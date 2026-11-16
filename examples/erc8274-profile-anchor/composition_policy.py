"""Consumer policy: anchor + retirement + require_anchor, as a PURE function over explicit inputs.

Everything here is SIMULATED input. AnchorRegistry has no retirement or revocation (no owner, no roles, one
function `anchor(bytes32)`), and this module does not invent one: a "retirement" is an event the consumer reads
from a source IT chooses to trust, modelled as a list of `Retirement(verifier_ref, block, emitter)`.

It does not prove that any verifier stops accepting anything in production. It returns the verdict a consumer
policy combining (1) first-seen anchor, (2) retirement from trusted emitters, (3) "anchor required" would give.

Block convention (documented, tested on both sides of the edge): a retirement at block B takes effect AT B.
A submission in block s is historical only if s < B; s >= B is rejected. Reason: a block-level policy cannot order
two events inside the same block, so the edge fails closed. "After block B" in the original control is covered
(s > B rejected); s == B is the consumer's choice and this is ours.
Anchor timing: with require_anchor=True an anchor later than the submission is rejected (ANCHOR_AFTER_SUBMISSION).
With require_anchor=False the verdict is unchanged (accept) but the reason says what was there: ANCHORED_OK means the
anchor was in the submission's block or earlier; ANCHORED_LATE means it came later. Precedence: a trusted retirement
decides the reason first (HISTORICAL_OK / RETIRED_AT_OR_BEFORE_SUBMISSION), so ANCHORED_LATE only labels the branch
without a retirement; HISTORICAL_OK therefore says nothing about anchor timing when require_anchor=False.
Inputs are block numbers already read at whatever finality the consumer's policy requires (not handled here).
"""
from typing import NamedTuple, Optional, Iterable

# Reason codes
UNANCHORED = "UNANCHORED"                                # require_anchor and no anchor event
ANCHOR_AFTER_SUBMISSION = "ANCHOR_AFTER_SUBMISSION"      # first anchor is later than the submission (not covered at that time)
RETIRED_AT_OR_BEFORE_SUBMISSION = "RETIRED_AT_OR_BEFORE_SUBMISSION"  # trusted retirement at block <= submission block
HISTORICAL_OK = "HISTORICAL_OK"                          # retired later, submission strictly before the retirement
ANCHORED_OK = "ANCHORED_OK"                              # anchor in the submission's block or earlier, no applicable retirement
ANCHORED_LATE = "ANCHORED_LATE"                          # require_anchor=False, anchor LATER than the submission, no applicable retirement
ANCHOR_NOT_REQUIRED = "ANCHOR_NOT_REQUIRED"              # unanchored, policy does not require an anchor, no retirement


class Retirement(NamedTuple):
    verifier_ref: str   # the anchor `ref` (or any consumer-chosen id) of the retired configuration
    block: int          # block at which the retirement takes effect (>= semantics, see module docstring)
    emitter: str        # who published it; only emitters the consumer trusts count


class Verdict(NamedTuple):
    accept: bool
    reason: str


def _blk(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ValueError(f"{name} must be a non-negative int block number")
    return v


def evaluate(verifier_ref: str, submission_block: int, anchor_block: Optional[int],
             retirements: Iterable[Retirement], trusted_emitters: Iterable[str],
             require_anchor: bool) -> Verdict:
    """anchor_block: first-seen block of this verifier's ref (None = no event in the window the consumer read)."""
    _blk("submission_block", submission_block)
    if anchor_block is not None:
        _blk("anchor_block", anchor_block)
    trusted = set(trusted_emitters)
    mine = []
    for r in retirements:
        _blk("retirement.block", r.block)
        if r.verifier_ref == verifier_ref and r.emitter in trusted:   # other verifiers / untrusted emitters are ignored
            mine.append(r.block)
    retired_at = min(mine) if mine else None                          # append-only: the earliest trusted retirement governs

    if anchor_block is None and require_anchor:
        return Verdict(False, UNANCHORED)
    if anchor_block is not None and anchor_block > submission_block and require_anchor:
        return Verdict(False, ANCHOR_AFTER_SUBMISSION)
    if retired_at is not None:
        if submission_block >= retired_at:
            return Verdict(False, RETIRED_AT_OR_BEFORE_SUBMISSION)
        return Verdict(True, HISTORICAL_OK)
    if anchor_block is None:
        return Verdict(True, ANCHOR_NOT_REQUIRED)
    if anchor_block > submission_block:
        return Verdict(True, ANCHORED_LATE)    # accepted only because no anchor is required; the label says the anchor was NOT there yet
    return Verdict(True, ANCHORED_OK)
