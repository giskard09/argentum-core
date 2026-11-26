"""Mutants for peer-reconciliation-ref: each one removes or loosens one rule of verify.py. A
corpus that passes a mutant does not show that the rule is checked.

    python3 mutants.py    # exit 0 iff every listed mutant is caught

A mutant is caught when at least one vector is not ok under score() (v1.3.1: a negative vector
must be rejected under its failure_mode, and not merely by disagreeing with its declared
checks). The same run under the pre-v1.3.1 scoring (any rejection counts) is printed beside it.

Not listed, with the reason (none of these is proven equivalent one by one):
  - the declared-value cross-checks (structural_validity, signature_binding, party_distinctness,
    comparator_state, `!= declared`): for a vector whose declared values equal what the spec
    computes, the mismatch line never fires, so removing it changes no verdict.
  - signed_fields empty: rejected by signature_binding in any case (an empty list covers none of
    the three required fields), so structural_validity's own empty check is redundant in outcome.
  - resolved_by absent (the `if not resolved_by` presence check): the next check, that resolved_by is
    a valid identifier, also rejects an absent value, so removing the presence check changes the
    message, not the verdict.
  - `supersedes` resolving to nothing (`prior is None` check removed): the verifier then raises
    instead of returning a verdict, which is a crash, not a mutant a vector can catch or miss.
  - signature_valid_* absent from `checks`: the spec does not say what an absent declaration means.
  - signature_binding's exemption for observed != true: no vector can tell the exemption from the
    evaluation, since a block with observed != true has no co_signer that could fail it.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "verify.py").read_text()

MUTANTS = {
    'b64-not-strict-struct':
        ('raw = base64.b64decode(pubkey, validate=True)', 'raw = base64.b64decode(pubkey, validate=False)'),
    're-match-not-fullmatch':
        ('PARTY_ID_RE.fullmatch(party_id)', 'PARTY_ID_RE.match(party_id)'),
    'party-id-allows-space':
        ('[\\x21-\\x7e]+', '[\\x20-\\x7e]+'),
    'party-id-allows-empty':
        ('[\\x21-\\x7e]+")', '[\\x21-\\x7e]*")'),
    'no-spki-prefix-check':
        (' or raw[:12] != SPKI_ED25519_PREFIX', ''),
    'len-check-loosened':
        ('len(raw) != 44', 'len(raw) < 44'),
    'struct-no-pubkey-check':
        ('        if pubkey_bytes(co_signer.get("pubkey")) is None:\n            return False\n', ''),
    'struct-unobserved-anything':
        ('return action_ref is None and co_signer is None', 'return True'),
    'struct-observed-truthy':
        ('    if observed is True:\n        if action_ref is None:', '    if observed:\n        if action_ref is None:'),
    'struct-co_signer-fields-any':
        ('if not all(co_signer.get(k) for k in required):', 'if not any(co_signer.get(k) for k in required):'),
    'binding-subset-to-intersect':
        ('return REQUIRED_SIGNED_FIELDS.issubset(set(signed_fields))', 'return bool(REQUIRED_SIGNED_FIELDS & set(signed_fields))'),
    'supersedes-skip-interaction-id':
        ('if prior.get("interaction_id") != envelope.get("interaction_id"):', 'if False:'),
    'supersedes-resolved_by-case-sensitive':
        ('if resolved_by.lower() in current_parties:', 'if resolved_by in current_parties:'),
    'supersedes-parties-case-sensitive':
        ('        pid.lower()\n        for pid in (envelope', '        pid\n        for pid in (envelope'),
    'supersedes-resolved_by-no-id-rule':
        ('    if not party_id_valid(resolved_by):\n        return False, (', '    if False:\n        return False, ('),
    'supersedes-self-resolve-allowed':
        ('    if resolved_by.lower() in current_parties:\n        return False, (', '    if False:\n        return False, ('),
    'distinct-case-sensitive-ids':
        ('ia.lower() == ib.lower()', 'ia == ib'),
    'distinct-pubkey-as-text':
        ('ka = pubkey_bytes((a.get("co_signer") or {}).get("pubkey"))\n        kb = pubkey_bytes((b.get("co_signer") or {}).get("pubkey"))', 'ka = (a.get("co_signer") or {}).get("pubkey")\n        kb = (b.get("co_signer") or {}).get("pubkey")'),
    'distinct-none-equals-none':
        ('if ka is not None and ka == kb:', 'if ka == kb:'),
    'distinct-and-to-or':
        ('if a.get("observed") is True and b.get("observed") is True:', 'if a.get("observed") is True or b.get("observed") is True:'),
    'distinct-never-fails':
        ('        return False\n    if a.get("observed") is True and b.get', '        pass\n    if a.get("observed") is True and b.get'),
    'comparator-ignore-distinct':
        ('if not (a_ready and b_ready and distinct):', 'if not (a_ready and b_ready):'),
    'comparator-ignore-bind_a':
        ('and sig_a_ok and bind_a', 'and sig_a_ok'),
    'comparator-ignore-sig_b':
        ('and sig_b_ok and bind_b', 'and bind_b'),
    'comparator-ignore-struct_a':
        ('a_ready = struct_a and ', 'a_ready = '),
    'comparator-agreed-inverted':
        ('if party_a["action_ref"] == party_b["action_ref"]:', 'if party_a["action_ref"] != party_b["action_ref"]:'),
    'canonical-ref-unchecked':
        ('if computed_ref != declared_ref:', 'if False:'),
    'distinct-failure-line-off':
        ('    if not distinct:\n        failures.append(', '    if False:\n        failures.append('),
    'sigvalidity-off':
        ('if party.get("observed") is True and not checks.get(f"signature_valid_{label}", False):', 'if False:'),
}


def run(src):
    ns = {"__file__": str(HERE / "verify.py"), "__name__": "mutant"}
    exec(compile(src, "verify_mutant.py", "exec"), ns)
    new, old = [], []
    for v in ns["load_vectors"]():
        conforms, _failures = ns["verify_vector"](v)
        if not ns["score"](v)[0]:
            new.append(v["id"])
        if (conforms if v["expected"] == "PASS" else not conforms) is False:
            old.append(v["id"])
    return new, old


def main() -> int:
    bad = 0
    new, old = run(SRC)
    print(f"unmutated verifier fails {len(new)} vector(s)")
    bad += bool(new)
    caught_new = caught_old = 0
    for name, (old_s, new_s) in MUTANTS.items():
        if SRC.count(old_s) != 1:
            print(f"BAD  {name}: mutation site not found exactly once")
            bad += 1
            continue
        hit_new, hit_old = run(SRC.replace(old_s, new_s, 1))
        caught_new += bool(hit_new)
        caught_old += bool(hit_old)
        print(f"{'caught' if hit_new else 'MISSED'}  {name}: {len(hit_new)} vector(s) now, {len(hit_old)} under the old scoring")
        bad += not hit_new
    print(f"\n{caught_new}/{len(MUTANTS)} caught under v1.3.1 scoring; {caught_old}/{len(MUTANTS)} under the old scoring")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
