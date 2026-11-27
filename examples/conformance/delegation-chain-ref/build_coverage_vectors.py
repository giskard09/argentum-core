"""Builds coverage-vectors.json for delegation-chain-ref: vectors for rules that no vector in
the other files exercised (a mutation run of verify.py left 13 of 31 mutants alive), and for the
two places where verify.py's canonicalization differed from RFC 8785 until 2026-11-26.

Additive: the other five vector files keep their bytes and verdicts. Expected results are written
here by hand from the spec, not computed by verify.py. delegation_chain_ref and leaf_action_ref are
computed WITHOUT verify.py: ASCII objects with json.dumps (sorted keys, no whitespace), and the two
canonicalization vectors from a canonical string written out by hand per RFC 8785 and hashed with
hashlib; the builder also asserts that the repo's jcs.py gives the same bytes.

Keys are derived from public seeds (SHA-256 of a label), test material only. Vectors run in order
(the replay registry carries across vectors within a file).

    python3 build_coverage_vectors.py          # rewrites coverage-vectors.json
    python3 build_coverage_vectors.py --check  # exit 1 if the file on disk differs
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

from nacl.signing import SigningKey

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent))
from jcs import jcs_bytes  # noqa: E402

OUT = HERE / "coverage-vectors.json"
TS = "2026-11-26T10:00:00.000Z"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ascii_canon(obj) -> bytes:
    """RFC 8785 for objects that hold only ASCII strings, integers, lists and objects."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seed_key(party: str) -> SigningKey:
    return SigningKey(sha(f"delegation-chain-ref coverage {party}".encode()).encode()[:32])


def pub_b64(party: str) -> str:
    return base64.b64encode(bytes(seed_key(party).verify_key)).decode()


def refs(chain_id, n):
    return [sha(f"{chain_id}#{i}".encode()) for i in range(n)]


def chain_and_vector(vid, description, hops, *, expected="PASS", failure_mode=None, chain_id=None,
                     refs_override=None, root=None, ext=None, dcr=..., leaf_ts=TS, leaf_ref_ts=TS,
                     signed=False, extra=None):
    """hops: list of (delegator, delegatee, scope)."""
    chain_id = chain_id or vid
    hop_refs = refs_override or refs(chain_id, len(hops))
    chain_hops = []
    for i, (delegator, delegatee, scope) in enumerate(hops):
        h = {"delegatee": delegatee, "delegator": delegator, "delegation_ref": hop_refs[i], "scope": scope}
        if signed:
            pre = ascii_canon({"chain_id": chain_id, "delegator": delegator, "delegatee": delegatee,
                               "scope": scope, "delegation_ref": hop_refs[i]})
            h["hop_signature"] = base64.b64encode(seed_key(delegator).sign(pre).signature).decode()
        chain_hops.append(h)
    last = hops[-1]
    leaf_pre = {"agent_id": last[1], "action_type": "payment.route", "scope": last[2], "timestamp": leaf_ts}
    leaf_for_ref = dict(leaf_pre, timestamp=leaf_ref_ts)
    chain = {
        "chain_id": chain_id,
        "hops": chain_hops,
        "leaf_action_ref": sha(ascii_canon(leaf_for_ref)),
        "root_delegator": root or hops[0][0],
        "scope": hops[0][2],
        "version": "delegation-chain-ref-v1",
    }
    if ext is not None:
        chain["ext"] = ext
    v = {"id": vid, "description": description, "expected": expected}
    if failure_mode:
        v["failure_mode"] = failure_mode
    v["chain_artifact"] = chain
    v["delegation_chain_ref"] = sha(ascii_canon(chain)) if dcr is ... else dcr
    v["leaf_preimage"] = leaf_pre
    v.update(extra or {})
    return v


def flip_last_hex(h):
    return h[:-1] + ("0" if h[-1] != "0" else "1")


V = []
A, B, C = "test-cov-a", "test-cov-b", "test-cov-c"

# --- scope narrowing: the 2026-10-10 erratum has a vector now -----------------------------------
V.append(chain_and_vector(
    "cov-scope-widening-not-enforced-001",
    "2026-10-10 erratum. The chain widens scope between hops (mycelium:payment, then mycelium:*), and the caller does NOT declare enforce_scope_narrowing. Narrowing is a policy-level opt-in (module docstring, point 5; delegation-chain-ref.md), so the verifier reports nothing about it and the chain is PASS. A verifier that enforces narrowing without being told to fails this vector.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:*")]))
V.append(chain_and_vector(
    "cov-scope-equal-001",
    "enforce_scope_narrowing declared. Two hops with the same scope: equal scopes are valid (narrowing is 'equal or a sub-namespace'). PASS.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], extra={"enforce_scope_narrowing": True}))
V.append(chain_and_vector(
    "cov-scope-prefix-sibling-001",
    "enforce_scope_narrowing declared. hops[1].scope 'mycelium:payment' starts with hops[0].scope 'mycelium:pay' but is not a sub-namespace of it (no ':' boundary): a sibling, not a narrowing. scope_widening.",
    [(A, B, "mycelium:pay"), (B, C, "mycelium:payment")], expected="FAIL", failure_mode="scope_widening",
    extra={"enforce_scope_narrowing": True, "failure_detail": "'mycelium:payment' is not under 'mycelium:pay:'"}))
V.append(chain_and_vector(
    "cov-scope-wildcard-sibling-001",
    "enforce_scope_narrowing declared. hops[0].scope 'mycelium:*' covers mycelium and its sub-namespaces only; hops[1].scope 'audit:read' is outside it. scope_widening.",
    [(A, B, "mycelium:*"), (B, C, "audit:read")], expected="FAIL", failure_mode="scope_widening",
    extra={"enforce_scope_narrowing": True, "failure_detail": "'audit:read' is not under 'mycelium:*'"}))

# --- base invariants with no vector before -------------------------------------------------------
V.append(chain_and_vector(
    "cov-dcr-mismatch-001",
    "Everything is valid except the declared delegation_chain_ref, whose last hex digit was changed. SHA-256(JCS(chain_artifact)) does not match it.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], expected="FAIL", failure_mode="delegation_chain_ref",
    dcr=flip_last_hex(sha(ascii_canon({"placeholder": 1}))), extra={"failure_detail": "declared delegation_chain_ref is not the hash of the chain"}))
# The declared value above must be the right hash with one digit changed: rebuilt below once the chain exists.
bad = V[-1]
bad["delegation_chain_ref"] = flip_last_hex(sha(ascii_canon(bad["chain_artifact"])))

V.append(chain_and_vector(
    "cov-chain-break-last-pair-001",
    "Three hops. hops[0]->hops[1] is continuous; hops[1].delegatee ('test-cov-c') is not hops[2].delegator ('test-cov-x'). The break is in the last pair, which a verifier that stops one pair early never sees.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment"), ("test-cov-x", "test-cov-d", "mycelium:payment")],
    expected="FAIL", failure_mode="chain_break", extra={"failure_detail": "hops[1].delegatee != hops[2].delegator"}))
V.append(chain_and_vector(
    "cov-root-anchoring-001",
    "root_delegator names 'test-cov-z' but hops[0].delegator is 'test-cov-a'. root_anchoring.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], expected="FAIL", failure_mode="root_anchoring",
    root="test-cov-z", extra={"failure_detail": "root_delegator != hops[0].delegator"}))
V.append(chain_and_vector(
    "cov-leaf-anchoring-001",
    "leaf_action_ref was computed from a leaf_preimage with timestamp 2026-11-26T09:00:00.000Z; the vector carries a leaf_preimage with 2026-11-26T10:00:00.000Z. The recomputed action_ref differs from chain.leaf_action_ref (the scope matches, so only leaf_anchoring fails).",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], expected="FAIL", failure_mode="leaf_anchoring",
    leaf_ref_ts="2026-11-26T09:00:00.000Z", extra={"failure_detail": "recomputed action_ref != leaf_action_ref"}))

# --- replay registry --------------------------------------------------------------------------
accepted = V[1]["chain_artifact"]   # cov-scope-equal-001, accepted above
V.append(chain_and_vector(
    "cov-replay-ref-reuse-001",
    "A new chain_id that reuses a hop delegation_ref already accepted (hops[0] of cov-scope-equal-001). Reusing a delegation_ref across a different chain is a replay.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], expected="FAIL", failure_mode="replay_detected",
    refs_override=[accepted["hops"][0]["delegation_ref"], sha(b"cov-replay-ref-reuse-001#1")],
    extra={"failure_detail": "delegation_ref already accepted under another chain_id"}))
V.append(chain_and_vector(
    "cov-replay-chain-id-reuse-001",
    "The chain_id of cov-scope-equal-001 again, with different delegation_refs. Resubmitting an accepted chain_id is a replay even when no delegation_ref repeats.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], expected="FAIL", failure_mode="replay_detected",
    chain_id="cov-scope-equal-001", refs_override=[sha(b"other#0"), sha(b"other#1")],
    extra={"failure_detail": "chain_id already accepted"}))

# --- a submission that was not accepted must not consume the registry -----------------------------
SIGNED_HOPS = [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")]
V.append(chain_and_vector(
    "cov-not-assessed-001",
    "Signed hops, no keys in the key set the caller gives and the set is not declared complete: the signatures are not assessed. NOT_ASSESSED, and the chain_id is NOT recorded (the submission was not accepted).",
    SIGNED_HOPS, expected="NOT_ASSESSED", chain_id="cov-not-assessed", signed=True, extra={"pubkeys": {}}))
V.append(chain_and_vector(
    "cov-not-assessed-then-accepted-001",
    "The same chain as cov-not-assessed-001, now with the keys. The signatures verify, so it is PASS. It must not be reported as a replay: the earlier submission was not accepted and recorded nothing.",
    SIGNED_HOPS, chain_id="cov-not-assessed", signed=True,
    extra={"pubkeys": {A: pub_b64(A), B: pub_b64(B)}}))

# --- RFC 8785 canonicalization ------------------------------------------------------------------
def hand_canonical(v_chain, ext_literal):
    """The canonical string of a chain_artifact written out by hand per RFC 8785: keys in UTF-16
    code unit order (chain_id < ext < hops < leaf_action_ref < root_delegator < scope < version;
    in a hop delegatee < delegation_ref < delegator < scope), no whitespace, literal UTF-8, numbers
    as in ECMAScript. `ext_literal` is the hand-written canonical text of the ext object."""
    hs = ",".join('{"delegatee":"%s","delegation_ref":"%s","delegator":"%s","scope":"%s"}'
                  % (h["delegatee"], h["delegation_ref"], h["delegator"], h["scope"]) for h in v_chain["hops"])
    return ('{"chain_id":"%s","ext":%s,"hops":[%s],"leaf_action_ref":"%s","root_delegator":"%s","scope":"%s","version":"%s"}'
            % (v_chain["chain_id"], ext_literal, hs, v_chain["leaf_action_ref"], v_chain["root_delegator"],
               v_chain["scope"], v_chain["version"]))


# U+1F600 is the surrogate pair D83D DE00 in UTF-16; U+FFFF is the single unit FFFF. By UTF-16
# code unit D83D < FFFF, so the emoji key sorts first; by code point U+FFFF < U+1F600, the reverse.
EXT_ASTRAL = {"￿": 2, "\U0001F600": 1}
ASTRAL_LITERAL = '{"\U0001F600":1,"￿":2}'
EXT_NUMBERS = {"s": 0.000001, "n": 1.0, "e": 1e21}
NUMBERS_LITERAL = '{"e":1e+21,"n":1,"s":0.000001}'

for vid, desc, ext, literal in (
    ("cov-jcs-astral-key-001",
     "RFC 8785 key order. chain_artifact carries an opaque ext object with two keys, U+FFFF and U+1F600. RFC 8785 orders keys by UTF-16 code unit, so U+1F600 (D83D DE00) comes before U+FFFF; ordering by code point gives the reverse and a different hash. delegation_chain_ref is the SHA-256 of the canonical string written out by hand in build_coverage_vectors.py. PASS.",
     EXT_ASTRAL, ASTRAL_LITERAL),
    ("cov-jcs-number-forms-001",
     "RFC 8785 numbers. chain_artifact carries an opaque ext object with 1.0, 0.000001 and 1e21. ECMAScript Number::toString (RFC 8785) writes them 1, 0.000001 and 1e+21; Python's repr gives 1.0, 1e-06 and 1e+21. delegation_chain_ref is the SHA-256 of the canonical string written out by hand in build_coverage_vectors.py. PASS.",
     EXT_NUMBERS, NUMBERS_LITERAL),
):
    v = chain_and_vector(vid, desc, [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], ext=ext, dcr="x")
    hand = hand_canonical(v["chain_artifact"], literal)
    assert hand.encode("utf-8") == jcs_bytes(v["chain_artifact"]), vid   # second route: the repo's jcs.py
    v["delegation_chain_ref"] = sha(hand.encode("utf-8"))
    V.append(v)

V.append(chain_and_vector(
    "cov-int-out-of-profile-001",
    "chain_artifact carries an opaque ext integer, 9007199254740993 (2^53 + 1), which an IEEE-754 double cannot hold. RFC 8785 numbers are doubles and the repo's jcs.py refuses it, so the chain cannot be canonicalized and the verifier reports a failure instead of hashing an exact integer or raising. The declared delegation_chain_ref is a placeholder.",
    [(A, B, "mycelium:payment"), (B, C, "mycelium:payment")], expected="FAIL", failure_mode="delegation_chain_ref",
    ext={"n": 9007199254740993}, dcr="0" * 64, extra={"failure_detail": "integer outside +/-(2^53-1)"}))

OUT_DOC = {
    "spec_version": "delegation-chain-ref-v1",
    "description": "Additive vectors for delegation-chain-ref: rules and branches that no vector in the other files exercised (the 2026-10-10 scope-narrowing erratum, base invariants, replay registry, a not-assessed submission that must not be recorded) and RFC 8785 canonicalization (key order outside the BMP, number forms, integers outside the JCS profile). Vectors MUST be run in order (replay registry state carries across vectors within this file). A vector may carry its own pubkeys and enforce_scope_narrowing; the file declares neither.",
    "vectors": V,
    "provenance": {"authored_by": "giskard09 (argentum-core)", "verification_mode": "asserted", "independently_reproduced_by": []},
}


def render() -> str:
    return json.dumps(OUT_DOC, indent=2, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if OUT.exists() and OUT.read_text() == render() else 1)
    OUT.write_text(render())
    print(f"{len(V)} vectors -> {OUT.name}")
