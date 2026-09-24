"""Conformance tests for docs/spec/trail-head-ref-v1.md.

Each negative case is caught by a different check (verdict + reason), so the
suite shows the verifier tells the attacks apart, not only that it rejects
them. Attacks follow the ones run in microsoft/autogen#7353: removal and
reorder (Yarmoluk), tail truncation (babyblueviper1).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from plugins.agt_evidence_anchor.action_ref import compute_action_ref  # noqa: E402
from plugins.agt_evidence_anchor.merkle import get_proof  # noqa: E402
from plugins.agt_evidence_anchor.trail_head import (  # noqa: E402
    append_entry, checkpoint_digest, compute_head, entry_preimage,
    make_checkpoint, seal_period, verify_trail,
)

AGENT = "agent-alpha"
OTHER = "agent-beta"
T1 = "2026-09-23T18:00:00.000Z"
T2 = "2026-09-23T19:00:00.000Z"


def _ref(i, agent=AGENT):
    return compute_action_ref(agent, "payments.transfer", "trail-head-test",
                              f"2026-09-23T17:{i:02d}:00.000Z")


def _log(n, agent=AGENT, agent_seq=False):
    log = []
    for i in range(1, n + 1):
        append_entry(log, agent, _ref(i, agent), agent_seq=i if agent_seq else None)
    return log


def _sealed(log, period_end=T1, other_log=None):
    """Checkpoint for `log` sealed with one other agent, returns (cp, proof, root)."""
    other_log = other_log or _log(2, OTHER)
    cps = [make_checkpoint(AGENT, period_end, log),
           make_checkpoint(OTHER, period_end, other_log)]
    root, tree, digests = seal_period(cps)
    cp = cps[0]
    return cp, get_proof(checkpoint_digest(cp), tree), root


def _recompute_from(log, start):
    """Attacker rewrite: renumber and re-hash every entry from index `start`."""
    out = [dict(e) for e in log[:start]]
    for e in log[start:]:
        seq = len(out) + 1
        prev = out[-1]["head"] if out else None
        pre = entry_preimage(AGENT, seq, e["action_ref"], prev, e.get("agent_seq"))
        new = dict(pre)
        del new["v"]
        new["head"] = compute_head(agent_id=AGENT, seq=seq, action_ref=e["action_ref"],
                                   prev_head=prev, agent_seq=e.get("agent_seq"))
        out.append(new)
    return out


# ── Positive ──────────────────────────────────────────────────────────────

def test_complete():
    log = _log(6)
    cp, proof, root = _sealed(log)
    r = verify_trail(log, cp, proof, root)
    assert (r["verdict"], r["completeness"]) == ("complete", "proven")
    assert r["root_anchoring"] == "not_checked"


def test_unsealed_tail():
    log = _log(4)
    cp, proof, root = _sealed(log)
    append_entry(log, AGENT, _ref(5))
    r = verify_trail(log, cp, proof, root)
    assert (r["verdict"], r["completeness"]) == ("complete_unsealed_tail",
                                                "proven_through_checkpoint")
    assert r["unsealed_entries"] == 1


def test_empty_period_still_seals():
    log = _log(3)
    cp1 = make_checkpoint(AGENT, T1, log)
    cp2 = make_checkpoint(AGENT, T2, log)  # no new entries in the period
    assert (cp1["seq"], cp1["head"]) == (cp2["seq"], cp2["head"])
    assert checkpoint_digest(cp1) != checkpoint_digest(cp2)
    cp, proof, root = _sealed(log, period_end=T2)
    assert verify_trail(log, cp, proof, root)["verdict"] == "complete"


def test_no_checkpoint_is_not_a_pass():
    r = verify_trail(_log(3))
    assert (r["verdict"], r["completeness"]) == ("continuity_only", "not_evaluated")


def test_agent_seq_contiguous_passes():
    log = _log(4, agent_seq=True)
    cp, proof, root = _sealed(log)
    assert verify_trail(log, cp, proof, root)["verdict"] == "complete"


def test_deterministic_heads():
    assert _log(5) == _log(5)


# ── Negative: each caught by a distinct check ─────────────────────────────

def _v(log, **kw):
    r = verify_trail(log, **kw)
    return r["verdict"], r["reason"], r["at_seq"]


def test_removal_without_rewrite_is_seq_gap():
    log = _log(6)
    assert _v(log[:2] + log[3:]) == ("broken", "seq_gap", 4)


def test_reorder_is_seq_order():
    log = _log(6)
    swapped = log[:2] + [log[3], log[2]] + log[4:]
    assert _v(swapped) == ("broken", "seq_order", 4)


def test_tampered_action_ref_is_head_mismatch():
    log = _log(4)
    log[1] = dict(log[1], action_ref=_ref(59))
    assert _v(log) == ("broken", "head_mismatch", 2)


def test_removal_with_renumber_is_link_mismatch():
    log = _log(5)
    # drop seq 3, renumber the next entry to 3 and re-hash it over its own
    # (stale) prev_head: internally consistent, wrong link.
    e = dict(log[3])
    pre = entry_preimage(AGENT, 3, e["action_ref"], e["prev_head"])
    e.update(seq=3, head=compute_head(agent_id=AGENT, seq=3,
                                      action_ref=e["action_ref"], prev_head=e["prev_head"]))
    assert pre["prev_head"] == log[2]["head"]
    assert _v(log[:2] + [e]) == ("broken", "link_mismatch", 3)


def test_tail_truncation_passes_continuity_alone():
    # The point made in autogen#7353: continuity cannot see a cut tail.
    log = _log(6)
    r = verify_trail(log[:4])
    assert (r["verdict"], r["completeness"]) == ("continuity_only", "not_evaluated")


def test_tail_truncation_caught_by_checkpoint():
    log = _log(6)
    cp, proof, root = _sealed(log)
    assert _v(log[:4], checkpoint=cp, proof=proof, root=root) == \
        ("truncated", "log_shorter_than_checkpoint", 5)


def test_full_rewrite_caught_by_checkpoint():
    # Attacker removes seq 3 and re-hashes everything after it: continuity
    # passes, the anchored head does not match.
    log = _log(6)
    cp, proof, root = _sealed(log)
    append_entry(log, AGENT, _ref(7))
    forged = _recompute_from(log[:2] + log[3:], 2)
    assert len(forged) == 6
    assert verify_trail(forged)["verdict"] == "continuity_only"
    assert _v(forged, checkpoint=cp, proof=proof, root=root) == \
        ("checkpoint_mismatch", "head_differs_from_checkpoint", 6)


def test_checkpoint_not_in_root():
    log = _log(3)
    cp, proof, root = _sealed(log)
    fake = dict(cp, head=log[1]["head"], seq=2)
    assert _v(log[:2], checkpoint=fake, proof=proof, root=root) == \
        ("checkpoint_unproven", "not_in_root", None)


def test_checkpoint_of_other_agent():
    log = _log(3)
    other = _log(2, OTHER)
    cps = [make_checkpoint(AGENT, T1, log), make_checkpoint(OTHER, T1, other)]
    root, tree, _ = seal_period(cps)
    cp_other = cps[1]
    proof = get_proof(checkpoint_digest(cp_other), tree)
    assert _v(log, checkpoint=cp_other, proof=proof, root=root) == \
        ("checkpoint_unproven", "checkpoint_other_agent", None)


def test_stale_checkpoint():
    log = _log(3)
    cp, proof, root = _sealed(log)
    r = verify_trail(log, cp, proof, root, now="2026-09-24T18:00:00.000Z",
                     max_checkpoint_age_s=2 * 3600)
    assert (r["verdict"], r["reason"]) == ("stale_checkpoint", "checkpoint_too_old")


def test_agent_seq_gap():
    # Operator dropped an action the agent had signed before it reached the
    # log, and re-chained cleanly: only the agent's own counter shows it.
    log = _log(5, agent_seq=True)
    kept = [dict(e) for e in log[:2]] + [dict(e) for e in log[3:]]
    forged = _recompute_from(kept, 2)
    assert _v(forged) == ("agent_gap", "agent_seq_not_contiguous", 3)


def test_agent_seq_tail_drop_is_a_documented_limit():
    # Documented limit (spec, "Agent-side counter"): dropping the agent's
    # latest signed actions leaves the remaining counters contiguous. Only
    # the agent's own last agent_seq reveals it.
    log = _log(5, agent_seq=True)
    r = verify_trail(log[:3])
    assert (r["verdict"], r["completeness"]) == ("continuity_only", "not_evaluated")
    assert log[:3][-1]["agent_seq"] == 3  # an agent holding agent_seq=5 would see the gap


def test_agent_seq_partial():
    log = _log(3, agent_seq=True)
    forged = _recompute_from([dict(log[0]), dict(log[1]),
                              {k: v for k, v in log[2].items() if k != "agent_seq"}], 2)
    assert _v(forged) == ("agent_gap", "agent_seq_partial", None)


def test_genesis_with_prev_head_is_malformed():
    log = _log(2)
    bad = [dict(log[0], prev_head=log[1]["head"])] + log[1:]
    assert _v(bad) == ("malformed", "entry_preimage", 1)


def test_mixed_agents_malformed():
    a, b = _log(2), _log(2, OTHER)
    assert _v([a[0], b[1]])[0:2] == ("malformed", "agent_mixed")


def test_seal_rejects_two_checkpoints_same_agent():
    log = _log(2)
    with pytest.raises(ValueError):
        seal_period([make_checkpoint(AGENT, T1, log), make_checkpoint(AGENT, T1, log)])


# ── Window: a log presented from seq k > 1 ────────────────────────────────
#
# Found by an internal cross-check against independent session-chain data:
# a window that starts from a prev_head taken from the presented records is
# certified by nothing, so a rewrite that also changes that prev_head looks
# identical to an honest window.

K = 5  # window = seq 5..8 of an 8-entry log


def _window(n=8, k=K, agent_seq=False):
    log = _log(n, agent_seq=agent_seq)
    return log, [dict(e) for e in log[k - 1:]]


def _anchor(log, k=K, period_end=T1):
    """Checkpoint at seq k-1, sealed in a period root: (anchor, proof, root)."""
    cp, proof, root = _sealed(log[:k - 1], period_end=period_end)
    return {"anchor": cp, "anchor_proof": proof, "anchor_root": root}


def _rechain_window(refs, start_seq, prev, agent_seqs=None):
    out = []
    for i, ref in enumerate(refs):
        a = agent_seqs[i] if agent_seqs else None
        pre = entry_preimage(AGENT, start_seq + i, ref, prev, a)
        new = dict(pre)
        del new["v"]
        new["head"] = compute_head(agent_id=AGENT, seq=start_seq + i, action_ref=ref,
                                   prev_head=prev, agent_seq=a)
        out.append(new)
        prev = new["head"]
    return out


def _w(entries, **kw):
    r = verify_trail(entries, from_seq=K, **kw)
    return r["verdict"], r["completeness"], r["reason"], r.get("window_anchor")


def test_window_certified_anchor_no_checkpoint():
    log, win = _window()
    assert _w(win, **_anchor(log)) == ("continuity_only", "not_evaluated",
                                       "no_checkpoint", "certified")


def test_window_uncertified_anchor_is_declared():
    log, win = _window()
    r = verify_trail(win, from_seq=K)
    assert (r["verdict"], r["completeness"]) == ("continuity_only", "not_evaluated")
    assert (r["from_seq"], r["window_anchor"]) == (K, "uncertified")


def test_window_with_tail_checkpoint_is_window_complete_not_complete():
    log, win = _window()
    cp, proof, root = _sealed(log, period_end=T2)
    for kw in ({}, _anchor(log)):
        r = verify_trail(win, cp, proof, root, from_seq=K, **kw)
        assert (r["verdict"], r["completeness"]) == ("window_complete", "proven_from_seq")
        assert r["from_seq"] == K


def test_window_unsealed_tail():
    log, win = _window()
    cp, proof, root = _sealed(log[:7], period_end=T2)
    r = verify_trail(win, cp, proof, root, from_seq=K, **_anchor(log))
    assert (r["verdict"], r["completeness"]) == ("window_complete_unsealed_tail",
                                                "proven_from_seq_through_checkpoint")
    assert r["unsealed_entries"] == 1


def test_window_rewrite_including_anchor():
    """The attacker re-chains seq 5..8 from a prev_head of its own choosing."""
    log, win = _window()
    fake = _rechain_window([_ref(40 + i) for i in range(4)], K, "ab" * 32)
    # Uncertified start and no checkpoint: indistinguishable (documented limit).
    assert _w(fake) == ("continuity_only", "not_evaluated", "no_checkpoint", "uncertified")
    # A certified anchor catches the changed start on its own.
    assert _w(fake, **_anchor(log)) == ("anchor_mismatch", "failed",
                                        "prev_head_differs_from_anchor", None)
    # A tail checkpoint catches it without an anchor.
    cp, proof, root = _sealed(log, period_end=T2)
    assert _w(fake, checkpoint=cp, proof=proof, root=root)[:3] == (
        "checkpoint_mismatch", "failed", "head_differs_from_checkpoint")


def test_window_rewrite_keeping_anchor_needs_tail_checkpoint():
    log, win = _window()
    fake = _rechain_window([_ref(40 + i) for i in range(4)], K, win[0]["prev_head"])
    assert _w(fake, **_anchor(log))[:3] == ("continuity_only", "not_evaluated", "no_checkpoint")
    cp, proof, root = _sealed(log, period_end=T2)
    assert _w(fake, checkpoint=cp, proof=proof, root=root, **_anchor(log))[:3] == (
        "checkpoint_mismatch", "failed", "head_differs_from_checkpoint")


def test_window_truncation():
    log, win = _window()
    assert _w(win[:2])[:3] == ("continuity_only", "not_evaluated", "no_checkpoint")
    cp, proof, root = _sealed(log, period_end=T2)
    assert _w(win[:2], checkpoint=cp, proof=proof, root=root)[:3] == (
        "truncated", "failed", "log_shorter_than_checkpoint")


def test_anchor_head_is_actually_compared():
    """A verifier that checks only the anchor's Merkle proof would pass this."""
    log, win = _window()
    bad = dict(make_checkpoint(AGENT, T1, log[:K - 1]), head="cd" * 32)
    root, tree, _ = seal_period([bad, make_checkpoint(OTHER, T1, _log(2, OTHER))])
    kw = {"anchor": bad, "anchor_proof": get_proof(checkpoint_digest(bad), tree),
          "anchor_root": root}
    assert _w(win, **kw)[0] == "anchor_mismatch"


def test_anchor_failures_are_distinct():
    log, win = _window()
    good = _anchor(log)
    assert verify_trail(win, from_seq=K, **_anchor(log, k=K - 1))["reason"] == "anchor_not_adjacent"
    assert verify_trail(win, from_seq=K, anchor=good["anchor"], anchor_proof=[],
                        anchor_root="00" * 32)["reason"] == "anchor_not_in_root"
    other = dict(good, anchor=dict(good["anchor"], agent_id=OTHER))
    assert verify_trail(win, from_seq=K, **other)["reason"] == "anchor_other_agent"
    assert verify_trail(win, from_seq=K, anchor={"v": "x"}, anchor_proof=[],
                        anchor_root="00" * 32)["reason"] == "anchor_shape"
    assert verify_trail(log, **good)["reason"] == "anchor_not_adjacent"  # from_seq=1


def test_checkpoint_before_window():
    log, win = _window()
    cp, proof, root = _sealed(log[:3], period_end=T2)
    r = verify_trail(win, cp, proof, root, from_seq=K)
    assert (r["verdict"], r["completeness"], r["reason"]) == (
        "continuity_only", "not_evaluated", "checkpoint_before_window")


def test_window_agent_seq_checks_contiguity_only():
    log, win = _window(agent_seq=True)
    assert win[0]["agent_seq"] == K  # does not start at 1, and need not
    assert _w(win)[0] == "continuity_only"
    refs = [e["action_ref"] for e in win]
    gap = _rechain_window(refs, K, win[0]["prev_head"], agent_seqs=[5, 6, 8, 9])
    r = verify_trail(gap, from_seq=K)
    assert (r["verdict"], r["reason"], r["at_seq"]) == ("agent_gap", "agent_seq_not_contiguous", 7)


def test_full_log_missing_its_head_is_not_a_window():
    """Without from_seq a log that starts at seq 5 stays a seq_gap."""
    log, win = _window()
    r = verify_trail(win)
    assert (r["verdict"], r["reason"], r["at_seq"]) == ("broken", "seq_gap", K)


def test_full_log_reports_genesis_scope():
    r = verify_trail(_log(3))
    assert (r["from_seq"], r["window_anchor"]) == (1, "genesis")
