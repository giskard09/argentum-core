"""Maps agent-evidence-vectors' authority-at-dispatch/v1 denied-dispatch
cases onto execution-join-ref-v1 decisions, run through this directory's own
verify.py -- astrogilda's ask on probityai/agent-evidence-vectors#349: "pin
agent-evidence-vectors==0.35.0 in argentum-core with a Dependabot entry.
Then a CI step maps its denied-dispatch cases onto execution-join-ref
decisions for verify.py, and each release reaches you as a bump PR."

WHAT "DENIED-DISPATCH CASES" MEANS HERE: the `authority-at-dispatch/v1`
corpus this package ships (corpora/vectors-authority-at-dispatch/) judges
one attempted dispatch under delegated authority against 8 checks in a
fixed order, named in `agent_evidence_vectors.authoritydispatch.CHECKS`.
14 cases total, 10 denied. Of those 10, only 3 share a reason --
`dispatch_not_approved` -- that execution-join-ref-v1 can actually speak
to: the dispatched tool/target/bytes differ from the ones approved. That
is exactly what this spec's invariant 6 (`effective_call_binding`) is
for -- a covering decision binds to a specific `action_ref`; a dispatch
whose own ref differs and lacks a SEPARATE covering decision for the
rewritten ref fails invariant 6, reported as
`EFFECTIVE_CALL_REBINDING_FAILED`.

WHAT IS DELIBERATELY NOT MAPPED, AND WHY: the other 7 denied reasons
(`grant_revoked`, `grant_expired`, `scope_amplified`, `authority_evidence_
stale`, `evidence_age_inconsistent`, `contract_id_missing`,
`contract_id_unknown`) are all properties of a MULTI-HOP DELEGATION CHAIN
and FRESHNESS WINDOW that execution-join-ref-v1's own preimage shapes
(action_ref / decision_id / attempt_id / result_id -- see this
directory's verify.py, REQUIRED_FIELDS) do not carry any field for at
all: no delegation hops, no revocation list, no evidence-age window.
Forcing any of them through `effective_call_binding` -- the only
invariant that could even be coerced to fire -- would be exactly the
overclaim this repo's own execution-join-ref-remora-bridge companion
already refused to make for its AR-04 case (policy/context changed,
reported `NOT_MODELED`, never forced through invariant 6, see that
repo's PROVENANCE.md). This script reports each of those 7 explicitly,
by name, as out of scope -- never silently skipped, never silently
"passed".

HOW THE PIN IS ACTUALLY EXERCISED, NOT JUST DECLARED: this script reads
the deny entries straight out of the INSTALLED package's own corpus
(`authoritydispatch.ROOT`, see below) and asks that same package's
reference reader (`verify()`) for its live decision+reason on each one,
treating a disagreement with what `MANIFEST.json` declares as a reported
failure (upstream drift), not a silently-absorbed difference. A
Dependabot bump to a later agent-evidence-vectors release therefore
re-exercises real package logic on every CI run of this file -- AND, since
nothing here is vendored, against whatever cases that release actually
ships (new deny reasons, edited edge cases, a changed count), not a
frozen snapshot of today's 10. Corrected per astrogilda's review
(probityai/agent-evidence-vectors#349): an earlier version of this
docstring claimed the package's own `ROOT` fallback (checking a sibling
`corpora/` next to the installed module, or two directories up) meant
the package itself didn't trust its wheel to ship the corpus at a fixed
path, and vendored copies of the 10 deny cases here as a result. That
claim was never checked against the actual wheels and was wrong: in both
pinned releases (0.35.0, 0.36.3) the primary branch of `ROOT` resolves
to `corpora/vectors-authority-at-dispatch` inside the installed package,
with `cases/` and `MANIFEST.json` right there -- confirmed by unzipping
both wheels and inspecting the path directly, not by running installed
code. Reading live from `ROOT` is strictly better for what this script
is actually for (tracking the upstream corpus via Dependabot), so the
vendored `record.json`/`dispatched.bin` copies are gone; `check_case_
integrity()` below still checks each installed case's files against
`MANIFEST.json`'s own declared digests, now as a guard against a
corrupted/partial install rather than a vendoring correctness claim.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "profiles"))
sys.path.insert(0, str(_HERE))

import jcs  # noqa: E402  (repo-root helper, same as verify.py)
from verify import verify_vector  # noqa: E402  (this directory's own reference verifier)

try:
    from agent_evidence_vectors import authoritydispatch
except ImportError:
    print("agent-evidence-vectors is not installed -- see requirements.txt in this directory")
    sys.exit(2)

FIXTURES = authoritydispatch.ROOT
VERSION = "execution-join-ref-v1"
MAPPED_REASON = "dispatch_not_approved"


def iso_to_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ref(preimage: dict) -> str:
    """Bare hex, no "sha256:" prefix -- this spec's own convention (see
    vectors.json's real envelopes/preimages: action_ref, decision_id,
    input_hash, output_hash are all unprefixed), unlike the sibling
    execution-join-ref-remora-bridge repo's ref(), which does prefix."""
    return sha256_hex(jcs.jcs_bytes(preimage, ensure_ascii=False))


def check_case_integrity(entry: dict, case_dir: Path) -> str | None:
    for name, expected_digest in entry["files"].items():
        actual = sha256_hex((case_dir / name).read_bytes())
        if actual != expected_digest:
            return f"{name}: installed file does not match MANIFEST.json's own recorded digest ({actual} != {expected_digest})"
    return None


def build_vector(record: dict, dispatched_bytes: bytes) -> dict:
    """Maps ONE dispatch_not_approved record onto execution-join-ref-v1's
    envelope/preimages shape. The decision covers only the APPROVED
    action_ref -- never the dispatched one -- which is exactly why
    effective_call_binding must come back False when action_ref and
    effective_action_ref differ.

    `ts_ms` is shared between action_preimage and effective_preimage
    (both set to the approval's own timestamp), not taken from
    `decisionTime` -- mutation-tested: using `decisionTime` for the
    effective preimage makes action_ref != effective_action_ref purely
    from the ~5-minute approval-to-dispatch gap, even on an UNCHANGED
    call (verified against this corpus's own allow-direct case, where
    approved and dispatched are byte-identical: that must map to
    effective_call_binding=True, and only does once both preimages
    share one timestamp -- the same convention execution-join-ref-
    remora-bridge's AR-00 already uses, where approved_action_ref_
    preimage and effective_action_ref_preimage share ts_ms exactly)."""
    grantee = record["delegation"][0]["grantee"]
    approved = record["approvedAction"]
    dispatch = record["dispatch"]
    shared_ts_ms = iso_to_ms(approved["approvedAt"])

    action_preimage = {
        "actor_id": grantee,
        "input_hash": approved["payloadSha256"],
        "scope": f'{approved["tool"]}:{approved["target"]}',
        "ts_ms": shared_ts_ms,
        "version": VERSION,
    }
    effective_preimage = {
        "actor_id": grantee,
        "input_hash": sha256_hex(dispatched_bytes),
        "scope": f'{dispatch["tool"]}:{dispatch["target"]}',
        "ts_ms": shared_ts_ms,
        "version": VERSION,
    }
    action_ref = ref(action_preimage)
    effective_ref = ref(effective_preimage)

    decision_preimage = {
        "action_ref": action_ref,
        "outcome": "permit",
        "policy_id": f'delegation:{record["delegation"][0]["grantId"]}',
        "ts_ms": shared_ts_ms,
        "version": VERSION,
    }
    decision_id = ref(decision_preimage)

    return {
        "id": f"authority-at-dispatch/{record['attempt']['attemptId']}",
        "envelope": {
            "action_ref": action_ref,
            "effective_action_ref": effective_ref,
            "decision_id": decision_id,
        },
        "preimages": {
            "action_ref": action_preimage,
            "effective_action_ref": effective_preimage,
            "decision_id": decision_preimage,
        },
    }


def main() -> None:
    manifest = json.loads((FIXTURES / "MANIFEST.json").read_text())
    deny_entries = [e for e in manifest["vectors"] if e["expected"]["decision"] == "deny"]

    mapped = 0
    out_of_scope: list[str] = []
    problems: list[str] = []

    for entry in deny_entries:
        case_dir = FIXTURES / "cases" / entry["id"]
        record_path = case_dir / "record.json"

        integrity_problem = check_case_integrity(entry, case_dir)
        if integrity_problem:
            problems.append(f"{entry['id']}: {integrity_problem}")
            continue

        record = json.loads(record_path.read_text())
        dispatched_bytes = (case_dir / record["dispatch"]["payloadFile"]).read_bytes()

        # Live cross-check against the INSTALLED package's own reference
        # reader -- the thing a Dependabot bump actually re-exercises.
        live = authoritydispatch.verify(record_path)
        if live != entry["expected"]:
            problems.append(
                f"{entry['id']}: vendored fixture expects {entry['expected']}, installed "
                f"agent-evidence-vectors says {live} -- upstream drift, not a mapping bug"
            )
            continue

        if live["reason"] != MAPPED_REASON:
            out_of_scope.append(
                f"{entry['id']} ({live['reason']}): NOT_MODELED -- execution-join-ref-v1's "
                "preimage carries no delegation, revocation, scope-chain or evidence-"
                "freshness field to check this against"
            )
            continue

        vector = build_vector(record, dispatched_bytes)
        conforms, failures, computed = verify_vector(vector)
        ok = (not conforms) and computed.get("effective_call_binding") is False
        print(f"  {'[OK]' if ok else '[FAIL]'} {entry['id']}: dispatch_not_approved -> "
              f"effective_call_binding={computed.get('effective_call_binding')} "
              f"({'EFFECTIVE_CALL_REBINDING_FAILED' if ok else failures})")
        if ok:
            mapped += 1
        else:
            problems.append(
                f"{entry['id']}: expected EFFECTIVE_CALL_REBINDING_FAILED "
                f"(effective_call_binding=False), got conforms={conforms} "
                f"computed={computed} failures={failures}"
            )

    print(f"\n{mapped} dispatch_not_approved case(s) mapped and confirmed EFFECTIVE_CALL_REBINDING_FAILED")
    print(f"{len(out_of_scope)} other real denied-dispatch reason(s) explicitly NOT_MODELED:")
    for line in out_of_scope:
        print(f"  - {line}")

    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for line in problems:
            print(f"  ! {line}")
        sys.exit(1)

    if mapped == 0:
        print("\nno dispatch_not_approved case was actually checked -- nothing was verified")
        sys.exit(1)


if __name__ == "__main__":
    main()
