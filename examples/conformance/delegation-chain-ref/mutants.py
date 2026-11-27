"""Mutants for delegation-chain-ref/verify.py: each removes or loosens one rule and must make at
least one vector fail (a mutant that raises counts as caught: it produces no verdict).

    python3 mutants.py    # needs PyNaCl, like verify.py; exit 0 iff every listed mutant is caught

Run over the six vector files verify.py's main() runs. Not listed, with the reason (neither proven
equivalent one by one):
  - the scoring in run_file (`ok = verdict in expected`, the failure_mode prefix check): turning
    them off cannot fail a corpus that is correct, so no vector can catch them; a vector that FAILs
    for another reason than its failure_mode would be a wrong vector.
  - the Ed25519 small-order and canonical-encoding behaviour: that is PyNaCl's (libsodium's), checked
    by ed25519-hardening/check_hardening.py, not by this file's code.
"""
import contextlib
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "verify.py").read_text()
FILES = ("vectors.json", "cross-org-vectors.json", "replay-vectors.json", "key-completeness-vectors.json",
         "small-order-key-vectors.json", "coverage-vectors.json")

MUTANTS = {
"dcr-unchecked": ("if expected_dcr is not None and expected_dcr != actual_dcr:", "if False:"),
"continuity-off": ('if hops[i]["delegatee"] != hops[i + 1]["delegator"]:', "if False:"),
"continuity-last-hop-skipped": ("for i in range(len(hops) - 1):", "for i in range(len(hops) - 2):"),
"root-anchoring-off": ('if chain["root_delegator"] != hops[0]["delegator"]:', "if False:"),
"leaf-block-skipped": ('if "leaf_preimage" in vector:', "if False:"),
"leaf-ref-compare-off": ('if computed_leaf != chain["leaf_action_ref"]:', "if False:"),
"leaf-scope-compare-off": ("if leaf_scope != leaf_hop_scope:", "if False:"),
"leaf-preimage-drops-timestamp": ('("agent_id", "action_type", "scope", "timestamp")', '("agent_id", "action_type", "scope")'),
"hop-sig-only-first-hop": ("for i, hop in enumerate(hops):\n        if \"hop_signature\" in hop:", "for i, hop in list(enumerate(hops))[:1]:\n        if \"hop_signature\" in hop:"),
"hop-sig-invalid-ignored": ("if sig == HOP_SIG_INVALID:", "if False:"),
"sig-preimage-drops-scope": ('        "scope": hop["scope"],\n        "delegation_ref"', '        "delegation_ref"'),
"sig-preimage-drops-chain_id": ('        "chain_id": chain_id,\n        "delegator"', '        "delegator"'),
"sig-preimage-drops-delegatee": ('        "delegatee": hop["delegatee"],\n        "scope"', '        "scope"'),
"sig-preimage-drops-delegator": ('        "delegator": hop["delegator"],\n        "delegatee"', '        "delegatee"'),
"unresolved-key-never-policy-fail": ("elif sig == HOP_SIG_KEY_UNRESOLVED and keys_are_complete:", "elif False:"),
"unresolved-key-not-reported": ("elif sig == HOP_SIG_KEY_UNRESOLVED:\n                not_assessed.append(", "elif False:\n                not_assessed.append("),
"unresolved-key-reported-as-invalid": ("    if not pub_b64:\n        return HOP_SIG_KEY_UNRESOLVED", "    if not pub_b64:\n        return HOP_SIG_INVALID"),
"narrowing-always-enforced": ("    if enforce_scope_narrowing:\n        for i in range(1, len(hops)):", "    if True:\n        for i in range(1, len(hops)):"),
"narrowing-never-enforced": ("    if enforce_scope_narrowing:\n        for i in range(1, len(hops)):", "    if False:\n        for i in range(1, len(hops)):"),
"narrowing-prefix-without-colon": ("return child_scope.startswith(parent_scope + \":\")", "return child_scope.startswith(parent_scope)"),
"narrowing-wildcard-accepts-anything": ("return child_scope == prefix or child_scope.startswith(prefix + \":\")", "return True"),
"narrowing-equal-scope-rejected": ("    if parent_scope == child_scope:\n        return True\n    if parent_scope.endswith", "    if False:\n        return True\n    if parent_scope.endswith"),
"narrowing-wildcard-off": ('    if parent_scope.endswith(":*"):', "    if False:"),
"replay-check-off": ("if seen_registry.contains(chain[\"chain_id\"], hop_refs):", "if False:"),
"replay-registry-chain_id-only": ("return chain_id in self.chain_ids or any(r in self.delegation_refs for r in hop_delegation_refs)", "return chain_id in self.chain_ids"),
"replay-registry-refs-only": ("return chain_id in self.chain_ids or any(r in self.delegation_refs for r in hop_delegation_refs)", "return any(r in self.delegation_refs for r in hop_delegation_refs)"),
"replay-recorded-even-on-failure": ("        elif not failures and not not_assessed:", "        else:"),
"replay-recorded-when-not-assessed": ("        elif not failures and not not_assessed:", "        elif not failures:"),
"replay-record-drops-refs": ("self.delegation_refs.update(hop_delegation_refs)", "pass"),
"not-assessed-never-verdict": ('    if not_assessed:\n        return "NOT_ASSESSED"', '    if False:\n        return "NOT_ASSESSED"'),
"jcs-back-to-sort_keys": ('    return jcs_bytes(obj).decode("utf-8")', '    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)'),
"jcs-out-of-profile-not-reported": ("    except (ValueError, TypeError) as e:\n        expected_dcr = None", "    except KeyError as e:\n        expected_dcr = None"),
}


def run(src):
    ns = {"__file__": str(HERE / "verify.py"), "__name__": "mutant"}
    exec(compile(src, "verify_mutant.py", "exec"), ns)
    failed = 0
    for f in FILES:
        with contextlib.redirect_stdout(io.StringIO()):
            _passed, bad = ns["run_file"](HERE / f)
        failed += bad
    return failed


def main() -> int:
    bad = 0
    base = run(SRC)
    print(f"unmutated verifier fails {base} vector(s)")
    bad += bool(base)
    caught = 0
    for name, (old, new) in MUTANTS.items():
        if SRC.count(old) != 1:
            print(f"BAD  {name}: mutation site not found exactly once")
            bad += 1
            continue
        try:
            failed, how = run(SRC.replace(old, new, 1)), ""
        except Exception as e:   # a verifier that raises gives no verdict
            failed, how = 1, f" (raised {type(e).__name__})"
        caught += failed > 0
        bad += failed == 0
        print(f"{'caught' if failed else 'MISSED'}  {name}: {failed} vector(s){how}")
    print(f"\n{caught}/{len(MUTANTS)} caught")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
