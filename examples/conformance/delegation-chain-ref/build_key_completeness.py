"""
Builds key-completeness-vectors.json: what a delegation-chain verifier reports when a hop's
delegator has no key in the key set it was given.

Keys are derived from public seeds (SHA-256 of a label) so anyone can rebuild the file
byte-identical. They are test material only and sign nothing outside this fixture.

    python3 build_key_completeness.py          # rewrites key-completeness-vectors.json
    python3 build_key_completeness.py --check  # exit 1 if the file on disk differs
"""

import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from nacl.signing import SigningKey

HERE = Path(__file__).parent

# Loaded by path: several conformance dirs ship a module named verify.
_spec = importlib.util.spec_from_file_location("delegation_chain_ref_verify", HERE / "verify.py")
_verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_verify)
compute_action_ref, hop_signing_preimage = _verify.compute_action_ref, _verify.hop_signing_preimage
jcs, sha256hex = _verify.jcs, _verify.sha256hex
OUT = HERE / "key-completeness-vectors.json"
PARTIES = ("test-kc-a", "test-kc-b", "test-kc-c")


def signing_key(party: str) -> SigningKey:
    return SigningKey(hashlib.sha256(f"delegation-chain-ref key-completeness {party}".encode()).digest())


def pub_b64(party: str) -> str:
    return base64.b64encode(bytes(signing_key(party).verify_key)).decode()


ATTACKER = SigningKey(hashlib.sha256(b"delegation-chain-ref key-completeness attacker").digest())


def chain(chain_id: str, forge_hop0: bool = False) -> tuple[dict, dict]:
    """a -> b -> c, every hop signed by its delegator (hop 0 by an attacker key if forge_hop0)."""
    leaf = {
        "agent_id": "test-kc-c",
        "action_type": "payment.route",
        "scope": "mycelium:payment",
        "timestamp": "2026-09-24T12:00:00.000Z",
    }
    hops = []
    for i, (delegator, delegatee) in enumerate((("test-kc-a", "test-kc-b"), ("test-kc-b", "test-kc-c"))):
        hop = {
            "delegator": delegator,
            "delegatee": delegatee,
            "scope": "mycelium:payment",
            "delegation_ref": sha256hex(f"{chain_id} hop {i}"),
        }
        key = ATTACKER if (forge_hop0 and i == 0) else signing_key(delegator)
        sig = key.sign(hop_signing_preimage(chain_id, hop).encode("utf-8")).signature
        hop["hop_signature"] = base64.b64encode(sig).decode()
        hops.append(hop)
    artifact = {
        "chain_id": chain_id,
        "hops": hops,
        "leaf_action_ref": compute_action_ref(leaf),
        "root_delegator": "test-kc-a",
        "scope": "mycelium:payment",
        "version": "delegation-chain-ref-v1",
    }
    return artifact, leaf


def vector(vid, description, expected, chain_id, pubkey_parties, keys_are_complete=None,
           failure_mode=None, forge_hop0=False):
    artifact, leaf = chain(chain_id, forge_hop0)
    v = {"id": vid, "description": description, "expected": expected}
    if failure_mode:
        v["failure_mode"] = failure_mode
    v["pubkeys"] = {p: pub_b64(p) for p in pubkey_parties}
    if keys_are_complete is not None:
        v["keys_are_complete"] = keys_are_complete
    v["chain_artifact"] = artifact
    v["delegation_chain_ref"] = sha256hex(jcs(artifact))
    v["leaf_preimage"] = leaf
    return v


def build() -> dict:
    return {
        "spec_version": "delegation-chain-ref-v1",
        "description": (
            "Key completeness. A delegator with no key in the given key set leaves that hop's "
            "signature unchecked: NOT_ASSESSED when the caller has not declared the key set "
            "complete, FAIL delegator_key_not_in_complete_key_set (a policy rejection, not a bad "
            "signature) when it has. One vector per form, plus a mixed vector where an unresolved "
            "key sits next to a signature that does not verify: the adverse finding decides, FAIL. "
            "Every vector carries its own pubkeys; keys_are_complete is set only where declared."
        ),
        "vectors": [
            vector(
                "kc-001-all-keys-present",
                "Control. Both delegators' keys are in the set and both hop signatures verify.",
                "PASS", "chain-kc-001", PARTIES,
            ),
            vector(
                "kc-002-key-absent-not-declared-complete",
                "test-kc-b's key is missing and completeness is not declared. Hop 1 is validly "
                "signed but cannot be checked here. FAIL would claim a finding the verifier did "
                "not make.",
                ["NOT_ASSESSED"], "chain-kc-002", ("test-kc-a", "test-kc-c"),
            ),
            vector(
                "kc-003-key-absent-declared-complete",
                "Same absence, key set declared complete by the caller. Rejected by policy; the "
                "reason code must not be hop_signature_invalid.",
                "FAIL", "chain-kc-003", ("test-kc-a", "test-kc-c"), keys_are_complete=True,
                failure_mode="delegator_key_not_in_complete_key_set",
            ),
            vector(
                "kc-004-mixed-forged-and-key-absent",
                "Hop 0 is signed by a key that is not test-kc-a's (forged) and test-kc-b's key is "
                "missing, completeness not declared. What could not be assessed does not mask what "
                "was found: FAIL hop_signature_invalid.",
                "FAIL", "chain-kc-004", ("test-kc-a", "test-kc-c"),
                failure_mode="hop_signature_invalid", forge_hop0=True,
            ),
        ],
    }


if __name__ == "__main__":
    text = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv[1:]:
        sys.exit(0 if OUT.read_text() == text else 1)
    OUT.write_text(text)
    print(f"wrote {OUT.name}")
