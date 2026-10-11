"""SQLite reservation and lifecycle checks for the durable worked-example guard."""

import importlib.util
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier, Event

import pytest


SET_DIR = Path(__file__).resolve().parent.parent / "examples/conformance/crewai-unguarded-retry"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"durable_test_{name}", SET_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DurableIdempotencyGuard = _load("durable_idempotency_guard").DurableIdempotencyGuard
EffectStore = _load("effect_store").EffectStore


@pytest.fixture
def effects(tmp_path):
    # EffectStore initializes its database destructively and owns a thread-bound
    # connection. Construct, write and close it exactly once in its owner thread.
    with ThreadPoolExecutor(max_workers=1) as executor:
        store = executor.submit(EffectStore, str(tmp_path / "effects.db")).result(timeout=10)
        try:
            yield store, executor
        finally:
            executor.submit(store.close).result(timeout=10)


def _apply(effects, action, attempt):
    store, executor = effects
    return executor.submit(store.apply_effect, action, attempt).result(timeout=10)


def _record(db_path, ref):
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(
            "SELECT trail_status, effect_id FROM guard_records WHERE idempotency_ref = ?",
            (ref,),
        ).fetchone()


@pytest.mark.parametrize(
    "refs, wait_for_commit",
    [(("same", "same"), False), (("first", "second"), False), (("same", "same"), True)],
    ids=["same-ref", "different-refs", "stale-read-after-commit"],
)
def test_concurrent_first_reads_reserve_one_effect_per_ref(tmp_path, effects, refs, wait_for_commit):
    db_path = str(tmp_path / "guard.db")
    barrier = Barrier(2)
    first_finished = Event()

    def worker(ref, attempt):
        guard = DurableIdempotencyGuard(db_path)
        read = guard._read
        snapshots = []

        def synchronized_first_read(key):
            snapshot = read(key)
            if not snapshots:
                snapshots.append(snapshot)
                # Delay the real snapshot, not the database read or its value.
                barrier.wait(timeout=10)
                if wait_for_commit and attempt == 2:
                    assert first_finished.wait(timeout=10)
            return snapshot

        guard._read = synchronized_first_read
        try:
            result = guard.guard(ref, attempt, lambda: _apply(effects, ref, attempt))
            return result, snapshots
        finally:
            guard.close()
            if attempt == 1:
                first_finished.set()

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(worker, ref, attempt) for attempt, ref in enumerate(refs, 1)]
        results = [future.result(timeout=15) for future in futures]

    assert all(snapshots == [None] for _, snapshots in results)
    store, _ = effects
    # Native read_independent opens fresh connections after both guards finish.
    observed = {ref: store.read_independent(ref) for ref in set(refs)}
    assert all(item["readable"] for item in observed.values())
    assert sum(item["effect_count"] for item in observed.values()) == len(set(refs))
    assert all(item["counter_value"] == len(set(refs)) for item in observed.values())
    outcomes = [result[1] for result, _ in results]
    assert outcomes.count("COMMITTED") == len(set(refs))
    assert all(_record(db_path, ref) == ("COMMITTED", item["effect_ids"][0]) for ref, item in observed.items())
    if wait_for_commit:
        assert outcomes == ["COMMITTED", "RECONCILED_GUARD"]
        assert results[0][0][0] == results[1][0][0]
    for ref, (result, _) in zip(refs, results):
        effect_id, outcome = result
        assert outcome in {"COMMITTED", "PENDING_GUARD", "RECONCILED_GUARD"}
        if outcome == "PENDING_GUARD":
            assert effect_id is None
        else:
            assert effect_id in observed[ref]["effect_ids"]


def test_pending_is_committed_before_effect(tmp_path, effects):
    db_path = str(tmp_path / "guard.db")
    guard = DurableIdempotencyGuard(db_path)

    def effect():
        assert _record(db_path, "action") == ("PENDING", None)
        return _apply(effects, "action", 1)

    try:
        effect_id, outcome = guard.guard("action", 1, effect)
    finally:
        guard.close()
    assert outcome == "COMMITTED"
    assert _record(db_path, "action") == ("COMMITTED", effect_id)
    assert effects[0].read_independent("action")["effect_ids"] == [effect_id]


@pytest.mark.parametrize("effect_committed", [False, True], ids=["before-effect", "after-effect"])
def test_exception_leaves_pending_for_fresh_instance(tmp_path, effects, effect_committed):
    db_path = str(tmp_path / "guard.db")
    first = DurableIdempotencyGuard(db_path)

    def interrupted_effect():
        if effect_committed:
            _apply(effects, "action", 1)
        raise RuntimeError("attempt interrupted")

    try:
        with pytest.raises(RuntimeError, match="attempt interrupted"):
            first.guard("action", 1, interrupted_effect)
    finally:
        first.close()
    assert _record(db_path, "action") == ("PENDING", None)

    fresh = DurableIdempotencyGuard(db_path)
    try:
        assert fresh.guard("action", 2, lambda: pytest.fail("PENDING must not dispatch")) == (None, "PENDING_GUARD")
    finally:
        fresh.close()
    observed = effects[0].read_independent("action")
    assert observed["readable"]
    assert observed["effect_count"] == int(effect_committed)
    assert observed["counter_value"] == int(effect_committed)
    assert _record(db_path, "action") == ("PENDING", None)


def test_fresh_instance_replays_committed_effect(tmp_path, effects):
    db_path = str(tmp_path / "guard.db")
    first = DurableIdempotencyGuard(db_path)
    try:
        effect_id, outcome = first.guard("action", 1, lambda: _apply(effects, "action", 1))
    finally:
        first.close()
    assert outcome == "COMMITTED"

    fresh = DurableIdempotencyGuard(db_path)
    try:
        assert fresh.guard("action", 2, lambda: pytest.fail("COMMITTED must replay")) == (effect_id, "RECONCILED_GUARD")
    finally:
        fresh.close()
    observed = effects[0].read_independent("action")
    assert observed["effect_ids"] == [effect_id]
    assert observed["counter_value"] == 1


def test_reconcile_requires_independent_effect_observation(tmp_path, effects):
    db_path = str(tmp_path / "guard.db")
    first = DurableIdempotencyGuard(db_path)

    def interrupted_effect():
        raise RuntimeError("before effect")

    try:
        with pytest.raises(RuntimeError, match="before effect"):
            first.guard("action", 1, interrupted_effect)
    finally:
        first.close()

    fresh = DurableIdempotencyGuard(db_path)
    store, _ = effects
    try:
        assert fresh.reconcile("action", "action", store) is None
        assert _record(db_path, "action") == ("PENDING", None)
        effect_id = _apply(effects, "action", 1)
        assert fresh.reconcile("action", "action", store) == effect_id
        assert fresh.guard("action", 2, lambda: pytest.fail("reconciled effect must replay")) == (effect_id, "RECONCILED_GUARD")
    finally:
        fresh.close()
    assert _record(db_path, "action") == ("COMMITTED", effect_id)
    observed = store.read_independent("action")
    assert observed["effect_ids"] == [effect_id]
    assert observed["counter_value"] == 1
