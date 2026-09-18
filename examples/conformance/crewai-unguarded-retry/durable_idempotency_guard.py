"""idempotency-ref-v1 guard, durable variant -- gap #3 (nsolland,
crewAIInc/crewAI#7449, mapped 2026-09-14: "resume tras restart pierde
estado").

`idempotency_guard.IdempotencyGuard` keeps its PENDING/COMMITTED records in
a plain `dict`. That is a property of the *process*, not of the action: if
the process crashes and restarts between an attempt leaving a record
PENDING and the retry that follows, the new process starts with an empty
dict. The retry finds no record at all -- not PENDING, not COMMITTED -- and
the guard treats it as a brand-new logical action, running the real effect
again. `guard()`/`reconcile()` correctly distinguish PENDING from COMMITTED
*within one process's memory*; nothing about that logic requires memory,
it only requires the record to still be there when the retry arrives.

This variant keeps the exact same lifecycle (`guard`, `reconcile`, the same
three `guard_outcome` values) and replaces the storage with a SQLite table,
so a record written by one process is still readable by a different
process (or the same process after a restart) reading the same path.
"""

from __future__ import annotations

import json
import os
import sqlite3


class DurableIdempotencyGuard:
    """PENDING/COMMITTED store keyed by idempotency_ref, persisted to disk.

    Same lifecycle as `idempotency_guard.IdempotencyGuard.guard()` /
    `.reconcile()` -- see that module's docstring for PENDING_GUARD /
    RECONCILED_GUARD semantics, which are unchanged here. The only
    difference is where the record lives: a row in `db_path`, read fresh
    on every call instead of a `dict` held in process memory.
    """

    def __init__(self, db_path: str, *, reset: bool = False) -> None:
        self.db_path = db_path
        if reset and os.path.exists(db_path):
            os.remove(db_path)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS guard_records ("
            "idempotency_ref TEXT PRIMARY KEY, "
            "trail_status TEXT NOT NULL, "
            "effect_id TEXT)"
        )
        self._conn.commit()
        self.events: list[dict] = []

    def _read(self, idempotency_ref: str) -> dict | None:
        row = self._conn.execute(
            "SELECT trail_status, effect_id FROM guard_records WHERE idempotency_ref = ?",
            (idempotency_ref,),
        ).fetchone()
        if row is None:
            return None
        return {"trail_status": row[0], "effect_id": row[1]}

    def _write(self, idempotency_ref: str, record: dict) -> None:
        self._conn.execute(
            "INSERT INTO guard_records (idempotency_ref, trail_status, effect_id) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(idempotency_ref) DO UPDATE SET "
            "trail_status = excluded.trail_status, effect_id = excluded.effect_id",
            (idempotency_ref, record["trail_status"], record["effect_id"]),
        )
        self._conn.commit()

    def guard(self, idempotency_ref: str, attempt_no: int, real_effect_fn):
        existing = self._read(idempotency_ref)

        if existing is not None and existing["trail_status"] == "COMMITTED":
            self.events.append(
                {"attempt_no": attempt_no, "guard_outcome": "RECONCILED_GUARD",
                 "idempotency_ref": idempotency_ref, "effect_id": existing["effect_id"]}
            )
            return existing["effect_id"], "RECONCILED_GUARD"

        if existing is not None and existing["trail_status"] == "PENDING":
            self.events.append(
                {"attempt_no": attempt_no, "guard_outcome": "PENDING_GUARD",
                 "idempotency_ref": idempotency_ref, "effect_id": None}
            )
            # Same discipline as the in-memory guard: a PENDING record found
            # on disk is exactly as authoritative as one found in memory --
            # it means some attempt (possibly a now-dead process) may have
            # already committed the effect. Refuse, do not re-run.
            return None, "PENDING_GUARD"

        self._write(idempotency_ref, {"trail_status": "PENDING", "effect_id": None})
        try:
            effect_id = real_effect_fn()
        except Exception:
            # Record stays PENDING on disk -- survives this process dying
            # right here, which is the scenario this fixture exists for.
            raise
        self._write(idempotency_ref, {"trail_status": "COMMITTED", "effect_id": effect_id})
        self.events.append(
            {"attempt_no": attempt_no, "guard_outcome": "COMMITTED",
             "idempotency_ref": idempotency_ref, "effect_id": effect_id}
        )
        return effect_id, "COMMITTED"

    def reconcile(self, idempotency_ref: str, logical_action_id: str, effect_store) -> str | None:
        """Provider-confirmed resolution of an orphaned PENDING record found
        on disk -- identical evidence rule as
        `idempotency_guard.IdempotencyGuard.reconcile`: only a fresh,
        independent read of `effect_store` counts, never elapsed time,
        and never a record's mere presence/absence across a restart."""
        existing = self._read(idempotency_ref)
        if existing is None or existing["trail_status"] != "PENDING":
            return None
        observed = effect_store.read_independent(logical_action_id)
        if not observed["readable"] or observed["effect_count"] == 0:
            return None
        real_effect_id = observed["effect_ids"][0]
        self._write(idempotency_ref, {"trail_status": "COMMITTED", "effect_id": real_effect_id})
        self.events.append(
            {"attempt_no": None, "guard_outcome": "RECONCILED_GUARD",
             "idempotency_ref": idempotency_ref, "effect_id": real_effect_id}
        )
        return real_effect_id

    def close(self) -> None:
        self._conn.close()
