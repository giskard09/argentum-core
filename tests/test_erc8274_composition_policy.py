"""Composition control proposed by Pavlo in the trustless-ai group (Telegram, 2026-11-16): anchor + retirement +
consumer policy. EVERYTHING IS SIMULATED: the retirement source is a list of events, there is no on-chain
retirement in AnchorRegistry, and no verifier is run. These tests check the verdicts of a consumer policy, not
the behavior of any verifier in production.
"""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "examples", "erc8274-profile-anchor", "composition_policy.py")
spec = importlib.util.spec_from_file_location("composition_policy", PATH)
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)

A, B_REF = "0x" + "aa" * 32, "0x" + "bb" * 32      # SYNTHETIC verifier refs
TRUSTED = {"consumer-trusted-source"}
BLOCK_B = 1000                                      # the retirement block "B" of the control
RET_A = [cp.Retirement(A, BLOCK_B, "consumer-trusted-source")]


def ev(ref, sub, anchor, rets=(), require=True, trusted=TRUSTED):
    return cp.evaluate(ref, sub, anchor, rets, trusted, require)


# step 1: anchored verifier, no retirement (regression)
def test_step1_anchored_accepted():
    assert ev(A, 900, 500) == (True, cp.ANCHORED_OK)

def test_step1_neg_anchor_after_submission_rejected():
    assert ev(A, 400, 500) == (False, cp.ANCHOR_AFTER_SUBMISSION)

def test_step1_edge_anchor_in_same_block_as_submission_accepted():
    # CONVENTION: anchor block <= submission block counts as covered (same-block order is unknowable at block level;
    # the anchor only bounds commitment, it does not authorize, so the lenient side is the safe one here).
    assert ev(A, 500, 500) == (True, cp.ANCHORED_OK)

def test_step1_edge_anchor_one_block_late_rejected():
    assert ev(A, 499, 500) == (False, cp.ANCHOR_AFTER_SUBMISSION)

def test_step1_design_late_anchor_labelled_not_rejected_when_anchor_not_required():
    # DESIGN CHOICE: with require_anchor=False a late anchor does not reject, but the reason says it was late.
    assert ev(A, 400, 500, require=False) == (True, cp.ANCHORED_LATE)

def test_step1_late_anchor_label_edge_same_block_is_ok_one_block_late_is_late():
    assert ev(A, 500, 500, require=False) == (True, cp.ANCHORED_OK)
    assert ev(A, 499, 500, require=False) == (True, cp.ANCHORED_LATE)

def test_step1_late_anchor_with_require_anchor_still_rejected():
    assert ev(A, 499, 500, require=True) == (False, cp.ANCHOR_AFTER_SUBMISSION)

def test_late_anchor_then_later_retirement_is_historical_late_anchor():
    # historical (submission < B) but the anchor was NOT there yet: the label must say so (accept unchanged).
    assert ev(A, 400, 500, RET_A, require=False) == (True, cp.HISTORICAL_LATE_ANCHOR)

def test_historical_label_edge_same_block_is_ok_one_block_late_is_late_anchor():
    assert ev(A, 500, 500, RET_A, require=False) == (True, cp.HISTORICAL_OK)
    assert ev(A, 499, 500, RET_A, require=False) == (True, cp.HISTORICAL_LATE_ANCHOR)

def test_historical_with_require_anchor_and_late_anchor_still_rejected():
    assert ev(A, 499, 500, RET_A, require=True) == (False, cp.ANCHOR_AFTER_SUBMISSION)

def test_historical_without_anchor_and_no_requirement_is_historical_ok():
    assert ev(A, 900, None, RET_A, require=False) == (True, cp.HISTORICAL_OK)

def test_late_anchor_after_retirement_rejected_by_retirement():
    assert ev(A, BLOCK_B + 1, BLOCK_B + 5, RET_A, require=False) == (False, cp.RETIRED_AT_OR_BEFORE_SUBMISSION)

# step 2: retire A at block B, activate verifier B
def test_step2_retirement_recorded_and_b_accepts_new():
    assert ev(B_REF, BLOCK_B + 1, BLOCK_B, RET_A) == (True, cp.ANCHORED_OK)           # B active, unaffected by A's retirement

def test_step2_neg_retirement_of_a_does_not_retire_b():
    assert ev(B_REF, BLOCK_B + 50, 10, RET_A)[0] is True                              # keyed by verifier ref

# step 3: NEW submission by A after block B is rejected although A's anchor is still valid
def test_step3_new_submission_after_b_rejected():
    assert ev(A, BLOCK_B + 1, 500, RET_A) == (False, cp.RETIRED_AT_OR_BEFORE_SUBMISSION)

def test_step3_neg_without_retirement_same_submission_accepted():
    assert ev(A, BLOCK_B + 1, 500, []) == (True, cp.ANCHORED_OK)                      # the retirement is what flips it

def test_step3_untrusted_emitter_retirement_ignored():
    rets = [cp.Retirement(A, BLOCK_B, "someone-else")]
    assert ev(A, BLOCK_B + 1, 500, rets) == (True, cp.ANCHORED_OK)                    # anyone can emit; only trusted counts

# step 4: OLD submission by A before block B stays verifiable
def test_step4_old_submission_historical_ok():
    assert ev(A, BLOCK_B - 1, 500, RET_A) == (True, cp.HISTORICAL_OK)

def test_step4_neg_old_submission_before_anchor_still_rejected():
    assert ev(A, 400, 500, RET_A) == (False, cp.ANCHOR_AFTER_SUBMISSION)              # historical != uncovered

# step 5: no anchor + policy requires anchor
def test_step5_unanchored_rejected_when_required():
    assert ev(A, 900, None) == (False, cp.UNANCHORED)

def test_step5_neg_unanchored_accepted_when_not_required():
    assert ev(A, 900, None, require=False) == (True, cp.ANCHOR_NOT_REQUIRED)

def test_unanchored_and_retired_still_rejected_when_required():
    assert ev(A, 900, None, RET_A)[1] == cp.UNANCHORED

# exact edge. CONVENTION: retirement takes effect AT block B; submission in B is rejected.
def test_edge_block_before_b_accepted():
    assert ev(A, BLOCK_B - 1, 500, RET_A)[0] is True

def test_edge_block_equal_b_rejected():
    assert ev(A, BLOCK_B, 500, RET_A) == (False, cp.RETIRED_AT_OR_BEFORE_SUBMISSION)

def test_edge_block_after_b_rejected():
    assert ev(A, BLOCK_B + 1, 500, RET_A)[0] is False

def test_earliest_trusted_retirement_governs():
    rets = RET_A + [cp.Retirement(A, BLOCK_B + 500, "consumer-trusted-source")]
    assert ev(A, BLOCK_B + 10, 500, rets)[0] is False                                 # a later duplicate does not un-retire

@pytest.mark.parametrize("bad", [
    lambda: ev(A, -1, 500), lambda: ev(A, True, 500), lambda: ev(A, 1.5, 500),
    lambda: ev(A, 10, -3), lambda: ev(A, 10, 500, [cp.Retirement(A, -1, "consumer-trusted-source")]),
])
def test_bad_input_rejected(bad):
    with pytest.raises(ValueError):
        bad()
