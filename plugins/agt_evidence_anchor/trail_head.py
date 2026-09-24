"""
trail-head-ref v1: session completeness for an agent's trail.

Reference implementation of docs/spec/trail-head-ref-v1.md.

Per-trail anchoring (action_ref, batch-anchor) proves that a given record
existed and was not altered. It does not prove that a presented list of
records is the WHOLE list: drop an entry, swap two, or cut the tail, and
every remaining record still verifies on its own. This module adds two
things on top, without changing action_ref:

1. A per-agent hash chain. Entry i carries a gapless `seq` and commits to
   the previous entry's head:

       head_i = SHA-256(JCS({"v", "agent_id", "seq", "action_ref",
                             "prev_head" (absent at seq 1),
                             "agent_seq" (optional)}))

   Continuity catches a removed or reordered entry. It cannot catch a cut
   tail: a genuinely shorter log and a truncated one have identical
   internal structure.

2. A periodic checkpoint, the external high-water mark:

       {"v", "agent_id", "period_end", "seq", "head"}

   One per agent per period, emitted EVEN WHEN THE PERIOD HAD NO NEW
   ENTRIES (same seq/head, new period_end), so that a missing checkpoint
   is itself a signal instead of being indistinguishable from an idle
   agent. All checkpoints of a period go under one Merkle root
   (merkle.py, unchanged) anchored with AnchorRegistry.anchor(bytes32).
   Once anchored, the operator can no longer serve a history shorter than
   what it committed to.

Verdicts are kept distinct on purpose (see verify-failure-mode-ref.md):
each failure has its own code, and "no checkpoint supplied" is reported as
completeness "not_evaluated", never folded into a pass.

What this module does NOT check (the caller must, see the spec):
- that the Merkle root was actually anchored on-chain (AnchorRegistry
  query, same as batch-anchor);
- that the checkpoint supplied is the latest one, taken from the anchor
  stream rather than chosen by whoever presents the log (the staleness
  check below only bounds how old it may be);
- the agent's signature over agent_seq (verified at ingest).
"""
from __future__ import annotations

import datetime
import hashlib
import os
import sys
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from jcs import jcs_bytes  # noqa: E402
from plugins.agt_evidence_anchor.merkle import build_merkle_tree, verify_inclusion  # noqa: E402

ENTRY_V = "trail-head-ref/v1"
CHECKPOINT_V = "trail-head-ref/v1/checkpoint"

# Completeness states. Only the first four are positive answers; the two
# window states cover seq >= from_seq only.
PROVEN = "proven"
PROVEN_THROUGH_CHECKPOINT = "proven_through_checkpoint"
PROVEN_FROM_SEQ = "proven_from_seq"
PROVEN_FROM_SEQ_THROUGH_CHECKPOINT = "proven_from_seq_through_checkpoint"
NOT_EVALUATED = "not_evaluated"
FAILED = "failed"


def _is_hex64(v) -> bool:
    if not isinstance(v, str) or len(v) != 64:
        return False
    try:
        bytes.fromhex(v)
    except ValueError:
        return False
    return v == v.lower()


def _sha256_jcs(obj: dict) -> str:
    return hashlib.sha256(jcs_bytes(obj)).hexdigest()


def _parse_ts(ts: str) -> datetime.datetime:
    if not isinstance(ts, str) or not ts.endswith("Z"):
        raise ValueError(f"not an RFC 3339 UTC timestamp: {ts!r}")
    return datetime.datetime.fromisoformat(ts[:-1] + "+00:00")


# ---------------------------------------------------------------------------
# Producer side
# ---------------------------------------------------------------------------

def entry_preimage(
    agent_id: str,
    seq: int,
    action_ref: str,
    prev_head: Optional[str] = None,
    agent_seq: Optional[int] = None,
) -> dict:
    """Preimage of one chain entry.

    prev_head MUST be absent at seq 1 and present at every later seq. It is
    omitted, not null, at genesis: null would change the JCS bytes (same
    rule as draft-farley-acta-signed-receipts §2.2 previousReceiptHash).
    """
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
        raise ValueError("seq must be an integer >= 1")
    if not _is_hex64(action_ref):
        raise ValueError("action_ref must be 64 lowercase hex chars")
    if (seq == 1) != (prev_head is None):
        raise ValueError("prev_head is absent exactly at seq 1")
    if prev_head is not None and not _is_hex64(prev_head):
        raise ValueError("prev_head must be 64 lowercase hex chars")
    pre = {"v": ENTRY_V, "agent_id": agent_id, "seq": seq, "action_ref": action_ref}
    if prev_head is not None:
        pre["prev_head"] = prev_head
    if agent_seq is not None:
        if not isinstance(agent_seq, int) or isinstance(agent_seq, bool) or agent_seq < 1:
            raise ValueError("agent_seq must be an integer >= 1")
        pre["agent_seq"] = agent_seq
    return pre


def compute_head(**kwargs) -> str:
    return _sha256_jcs(entry_preimage(**kwargs))


def append_entry(log: list[dict], agent_id: str, action_ref: str,
                 agent_seq: Optional[int] = None) -> dict:
    """Append one entry to an agent's log (in memory) and return it."""
    seq = len(log) + 1
    prev = log[-1]["head"] if log else None
    pre = entry_preimage(agent_id, seq, action_ref, prev, agent_seq)
    entry = dict(pre)
    del entry["v"]
    entry["head"] = _sha256_jcs(pre)
    log.append(entry)
    return entry


def make_checkpoint(agent_id: str, period_end: str, log: list[dict]) -> dict:
    """Checkpoint of an agent's log at the end of a period.

    Call it every period, including periods with no new entries: the
    checkpoint then repeats seq/head with a later period_end.
    """
    if not log:
        raise ValueError("no checkpoint for an agent with no entries")
    _parse_ts(period_end)
    last = log[-1]
    return {"v": CHECKPOINT_V, "agent_id": agent_id, "period_end": period_end,
            "seq": last["seq"], "head": last["head"]}


def checkpoint_digest(cp: dict) -> str:
    return _sha256_jcs(cp)


def seal_period(checkpoints: list[dict]):
    """Merkle tree over the period's checkpoint digests, sorted by agent_id.

    Returns (root_hex, tree, digests_in_leaf_order). The root is what goes to
    AnchorRegistry.anchor(bytes32).
    """
    ordered = sorted(checkpoints, key=lambda c: c["agent_id"])
    ids = [c["agent_id"] for c in ordered]
    if len(set(ids)) != len(ids):
        raise ValueError("one checkpoint per agent per period")
    ends = {c["period_end"] for c in ordered}
    if len(ends) != 1:
        raise ValueError("all checkpoints in a seal share one period_end")
    digests = [checkpoint_digest(c) for c in ordered]
    tree = build_merkle_tree(digests)
    return tree.root, tree, digests


# ---------------------------------------------------------------------------
# Verifier side
# ---------------------------------------------------------------------------

def _result(verdict, completeness, at_seq=None, reason=None, **extra):
    r = {"verdict": verdict, "completeness": completeness,
         "at_seq": at_seq, "reason": reason,
         "root_anchoring": "not_checked"}
    r.update(extra)
    return r


def verify_trail(
    entries: list[dict],
    checkpoint: Optional[dict] = None,
    proof: Optional[list[str]] = None,
    root: Optional[str] = None,
    now: Optional[str] = None,
    max_checkpoint_age_s: Optional[int] = None,
    anchor: Optional[dict] = None,
    anchor_proof: Optional[list[str]] = None,
    anchor_root: Optional[str] = None,
    from_seq: int = 1,
) -> dict:
    """Check an agent's presented log for continuity and, given an anchored
    checkpoint, for completeness.

    entries: the log in presented order, from seq `from_seq`.
    from_seq: 1 for a full log (the default). A window starting at seq k > 1
      is verified only when the caller asks for it with from_seq=k, so a
      full log missing its first records is still a seq_gap, never a window
      (see "Window verification" in the spec).
    checkpoint/proof/root: the checkpoint, its Merkle proof and the period
      root. The caller confirms separately that `root` is anchored on-chain
      and that this is the latest checkpoint for the agent.
    now/max_checkpoint_age_s: optional staleness bound for the checkpoint.
    anchor/anchor_proof/anchor_root: for a window only, a checkpoint at seq
      k-1 with its Merkle proof and period root. It certifies the window's
      first prev_head. Without it the window's start is uncertified: taken
      from the presented records, which is the party being checked.

    Each failure has its own verdict; the first failing check wins.
    """
    # 1. shape
    if not isinstance(entries, list) or not entries:
        return _result("malformed", FAILED, reason="empty_or_not_a_list")
    agent_id = entries[0].get("agent_id") if isinstance(entries[0], dict) else None
    for e in entries:
        if not isinstance(e, dict) or not _is_hex64(e.get("head")) \
                or not _is_hex64(e.get("action_ref")) \
                or not isinstance(e.get("seq"), int) or isinstance(e.get("seq"), bool):
            return _result("malformed", FAILED, reason="entry_shape")
        if e.get("agent_id") != agent_id:
            return _result("malformed", FAILED, at_seq=e.get("seq"), reason="agent_mixed")

    # 2. continuity: seq order, then each head, then each link.
    # A reorder is told apart from a removal up front: the same contiguous
    # seq set k..k+n-1 presented out of order is "seq_order", a missing or
    # duplicated seq is "seq_gap". k is 1 for a full log, > 1 for a window.
    if not isinstance(from_seq, int) or isinstance(from_seq, bool) or from_seq < 1:
        raise ValueError("from_seq must be an integer >= 1")
    seqs = [e["seq"] for e in entries]
    if sorted(seqs) == list(range(from_seq, from_seq + len(seqs))) and seqs != sorted(seqs):
        first_bad = next(s for i, s in enumerate(seqs) if s != from_seq + i)
        return _result("broken", FAILED, at_seq=first_bad, reason="seq_order")
    prev_seq, prev_head = from_seq - 1, None
    for e in entries:
        seq = e["seq"]
        if seq != prev_seq + 1:
            return _result("broken", FAILED, at_seq=seq, reason="seq_gap")
        stated_prev = e.get("prev_head")
        try:
            pre = entry_preimage(agent_id, seq, e["action_ref"], stated_prev,
                                 e.get("agent_seq"))
        except ValueError:
            return _result("malformed", FAILED, at_seq=seq, reason="entry_preimage")
        if _sha256_jcs(pre) != e["head"]:
            return _result("broken", FAILED, at_seq=seq, reason="head_mismatch")
        if seq > from_seq and stated_prev != prev_head:
            return _result("broken", FAILED, at_seq=seq, reason="link_mismatch")
        prev_seq, prev_head = seq, e["head"]

    # 2e. window start. A full log starts at genesis. A window's first
    # prev_head is certified only by an anchor checkpoint at seq k-1 proven
    # in a period root; the presented records cannot certify themselves.
    if anchor is not None:
        if not isinstance(anchor, dict) or anchor.get("v") != CHECKPOINT_V \
                or not _is_hex64(anchor.get("head")) \
                or not isinstance(anchor.get("seq"), int) or isinstance(anchor.get("seq"), bool):
            return _result("anchor_unproven", FAILED, reason="anchor_shape")
        if anchor.get("agent_id") != agent_id:
            return _result("anchor_unproven", FAILED, reason="anchor_other_agent")
        if anchor_root is None or anchor_proof is None or \
                not verify_inclusion(checkpoint_digest(anchor), anchor_proof, anchor_root):
            return _result("anchor_unproven", FAILED, reason="anchor_not_in_root")
        if from_seq == 1 or anchor["seq"] != from_seq - 1:
            return _result("anchor_unproven", FAILED, at_seq=from_seq,
                           reason="anchor_not_adjacent")
        if entries[0]["prev_head"] != anchor["head"]:
            return _result("anchor_mismatch", FAILED, at_seq=from_seq,
                           reason="prev_head_differs_from_anchor")
        window_anchor = "certified"
    else:
        window_anchor = "genesis" if from_seq == 1 else "uncertified"
    scope = {"from_seq": from_seq, "window_anchor": window_anchor}

    # 3. agent-side counter, if the agent supplied one
    with_agent_seq = [e for e in entries if "agent_seq" in e]
    if with_agent_seq:
        if len(with_agent_seq) != len(entries):
            return _result("agent_gap", FAILED, reason="agent_seq_partial")
        # A window cannot know the agent_seq of seq k-1 (the anchor does
        # not carry it): only contiguity inside the window is checked.
        if from_seq == 1 and entries[0]["agent_seq"] != 1:
            return _result("agent_gap", FAILED, at_seq=1,
                           reason="agent_seq_not_contiguous")
        for a, b in zip(entries, entries[1:]):
            if b["agent_seq"] != a["agent_seq"] + 1:
                return _result("agent_gap", FAILED, at_seq=b["seq"],
                               reason="agent_seq_not_contiguous")

    last_seq = entries[-1]["seq"]

    # 4. completeness needs an external checkpoint
    if checkpoint is None:
        return _result("continuity_only", NOT_EVALUATED, reason="no_checkpoint",
                       last_seq=last_seq, **scope)

    if not isinstance(checkpoint, dict) or checkpoint.get("v") != CHECKPOINT_V \
            or not _is_hex64(checkpoint.get("head")) \
            or not isinstance(checkpoint.get("seq"), int):
        return _result("malformed", FAILED, reason="checkpoint_shape")
    if checkpoint.get("agent_id") != agent_id:
        return _result("checkpoint_unproven", FAILED, reason="checkpoint_other_agent")
    if root is None or proof is None or \
            not verify_inclusion(checkpoint_digest(checkpoint), proof, root):
        return _result("checkpoint_unproven", FAILED, reason="not_in_root")

    if max_checkpoint_age_s is not None and now is not None:
        age = (_parse_ts(now) - _parse_ts(checkpoint["period_end"])).total_seconds()
        if age > max_checkpoint_age_s:
            return _result("stale_checkpoint", FAILED, reason="checkpoint_too_old",
                           checkpoint_age_s=int(age))

    cp_seq = checkpoint["seq"]
    if cp_seq < from_seq:
        # The latest checkpoint predates the window: nothing presented is sealed.
        return _result("continuity_only", NOT_EVALUATED,
                       reason="checkpoint_before_window", last_seq=last_seq,
                       checkpoint_seq=cp_seq, **scope)
    if last_seq < cp_seq:
        return _result("truncated", FAILED, at_seq=last_seq + 1,
                       reason="log_shorter_than_checkpoint",
                       last_seq=last_seq, checkpoint_seq=cp_seq)
    if entries[cp_seq - from_seq]["head"] != checkpoint["head"]:
        return _result("checkpoint_mismatch", FAILED, at_seq=cp_seq,
                       reason="head_differs_from_checkpoint")
    # A matching head at cp_seq commits, through the chain, to every window
    # record up to it AND to the window's first prev_head: the checkpoint
    # certifies the anchor transitively. It says nothing about seq < k, so a
    # window gets its own positive verdicts, never "complete".
    window = from_seq > 1
    if last_seq == cp_seq:
        return _result("window_complete" if window else "complete",
                       PROVEN_FROM_SEQ if window else PROVEN,
                       last_seq=last_seq, as_of=checkpoint["period_end"], **scope)
    return _result("window_complete_unsealed_tail" if window else "complete_unsealed_tail",
                   PROVEN_FROM_SEQ_THROUGH_CHECKPOINT if window else PROVEN_THROUGH_CHECKPOINT,
                   last_seq=last_seq, checkpoint_seq=cp_seq,
                   unsealed_entries=last_seq - cp_seq,
                   as_of=checkpoint["period_end"], **scope)
