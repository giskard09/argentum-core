"""
Translate two real MoltyCel/aae-conformance-vectors (tag v1.0.0, commit
22a08d76ef76fda19274a687081523443e2ce7d0) into delegation-chain-ref-v1
fixtures, so this repo's own verifier (verify.py / verify_enforcement.py)
can be run against the same real-world scenarios MoltyCel's AAE verifier
rejects.

This is a translation, not a port. AAE (draft-kroehl-agentic-trust-aae-00)
and delegation-chain-ref-v1 are different formats with different trust
models -- see docs/spec/delegation-chain-ref.md:17 ("no vector in this
repository is an AAE conformance test"). Running these two translated
vectors through our verifier does not test AAE conformance and does not
claim our format implements AAE; it tests whether our verifier reaches the
same real-world verdict (REJECT/PASS) that MoltyCel's verifier reaches on
MoltyCel's own scenario, once that scenario is expressed in our terms.

What is NOT carried over, by design (declared here once, not per-vector):

  - AAE's JWS envelope (alg=EdDSA, cty=aae+json) and its signature. We
    decode the JWT header/payload to read the claims; we never verify the
    JWS signature, and we never fabricate a new signature over the
    translated hop to make hop_signature_valid pass. AAE's signature
    covers the VC2 JWT payload; our hop_signature_valid (verify.py) covers
    JCS({chain_id, delegator, delegatee, scope, delegation_ref}) -- a
    different preimage over a different artifact. The two are not
    substitutable. Translated hops carry no "hop_signature" field, so
    verify.py's invariant 5 is simply not assessed for them (optional
    field, per verify.py's own comment) -- we do not claim cryptographic
    authentication was checked for these two vectors.

  - AAE's narrowing dimension. AAE narrows authority via action-set subset
    (depth-1 in vector 11 drops "book", keeps only "read") and constraint
    tightening (max_transaction_value 500 -> 300); delegation-chain-ref-v1
    narrows via a colon-namespaced `scope` string prefix
    (monotonic_scope_narrowing). AAE's depth-1 mandate in vector 11 has no
    "scope" field at all. The translated hop below carries the parent's
    scope forward unchanged (equal, which scope_is_narrower_or_equal
    allows) -- this demonstrates that our structural check does not
    object, not that we evaluated AAE's actual narrowing. This is a real
    difference in what each format checks, not a translation bug.

  - AAE's `single_use` as an opt-in, per-credential flag. Our replay
    protection (SeenRegistry) is unconditional for every accepted chain --
    there is no analogous "this grant may be reused" declaration in
    delegation-chain-ref-v1. The vector-05 translation below reproduces
    the concrete scenario (same id presented after already being
    recorded), not the opt-in semantics.

  - `revoked_at` on the translated revocation_artifact for vector 11. AAE's
    revocation_responses reports a boolean (`revoked: true`) with no
    timestamp. enforce_7_5() (verify_enforcement.py) does not read
    revoked_at for its decision -- it only tests membership of
    revoked_action_ref -- so this is inert for the verdict, but a
    revocation-ref-v1 object conventionally carries one. We use the
    vector's own `context.current_time` as a stand-in and say so; it is
    not data MoltyCel supplied.

  - chain_id and delegation_ref values. AAE has no single "chain_id", and
    its delegator_aae_hash is AAE's own hash of its own VC bytes under a
    different algorithm -- not reusable as our delegation_ref. Every
    chain_id/delegation_ref/delegation_chain_ref value below is computed
    by us, over our own translated fields, using this repo's own jcs()/
    sha256hex() (imported from verify.py so there is exactly one
    implementation of those functions in this directory tree).
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # delegation-chain-ref/
from verify import compute_action_ref, jcs, sha256hex  # noqa: E402


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded)


def decode_jws(token: str) -> tuple[dict, dict]:
    """Decodes a JWS compact serialization's header and payload. Does not
    verify the signature -- see module docstring."""
    header_b64, payload_b64, _signature_b64 = token.split(".")
    header = json.loads(_b64url_decode(header_b64))
    payload = json.loads(_b64url_decode(payload_b64))
    return header, payload


def normalize_timestamp(aae_timestamp: str) -> str:
    """AAE timestamps in these vectors have second precision ("...12:00:00Z").
    This repo's convention (every existing fixture in delegation-chain-ref/)
    uses millisecond precision ("...12:00:00.000Z"). Translation only --
    AAE does not require millisecond precision and this is not a claim
    that it does."""
    if "." in aae_timestamp:
        return aae_timestamp
    assert aae_timestamp.endswith("Z"), f"unexpected AAE timestamp shape: {aae_timestamp!r}"
    return aae_timestamp[:-1] + ".000Z"


def mandate_of(payload: dict) -> dict:
    return payload["credentialSubject"]["aae"]["mandate"]


def make_hop(delegator: str, delegatee: str, scope: str, source_aae_id: str) -> dict:
    """delegation_ref is computed by us over the translated edge, tagged with
    the AAE credential id that authorized it (source_aae_id) for traceability
    back to the source vector -- source_aae_id is not part of
    delegation-chain-ref-v1's own schema, it is this translation's own
    provenance field, carried in the hop only so a reviewer can check the
    mapping; it does not affect any verify.py invariant."""
    delegation_ref = sha256hex(jcs({
        "delegator": delegator,
        "delegatee": delegatee,
        "scope": scope,
        "source_aae_id": source_aae_id,
    }))
    return {
        "delegator": delegator,
        "delegatee": delegatee,
        "scope": scope,
        "delegation_ref": delegation_ref,
        "source_aae_id": source_aae_id,
    }


def translate_vector_11(source: dict) -> dict:
    """MoltyCel aae-vector-11 (delegation-cascade-revocation) -> delegation-
    chain-ref-v1 chain_artifact + leaf_preimage + revocation_artifact.

    Scenario (unchanged from the source vector): enterprise-corp grants a
    root AAE to agent-a (actions read+book, scope travel-vertical); agent-a
    delegates to agent-b at depth 1 (actions read only, no "scope" field in
    AAE's depth-1 mandate -- see module docstring). The root AAE is
    reported revoked. Depth-1 presents a "read" action under it.
    """
    root_token = source["input"]["context"]["delegation_chain"][0]
    depth1_token = source["input"]["secured_aae"]
    _, root_payload = decode_jws(root_token)
    _, depth1_payload = decode_jws(depth1_token)

    root_mandate = mandate_of(root_payload)
    root_id = root_payload["id"]
    root_delegator = root_mandate["principal_did"]
    root_delegatee = root_payload["credentialSubject"]["id"]
    root_scope = root_mandate["scope"]

    depth1_id = depth1_payload["id"]
    depth1_delegator = depth1_payload["issuer"]
    assert depth1_delegator == root_delegatee, (
        "depth-1 issuer must be the root grant's delegatee -- if this ever "
        "fails against a future MoltyCel vector, the chain shape assumed "
        "below (issuer-chains-to-previous-credentialSubject) no longer holds"
    )
    depth1_delegatee = depth1_payload["credentialSubject"]["id"]
    depth1_scope = root_scope  # carried forward -- AAE's depth-1 mandate has no "scope" key

    hop0 = make_hop(root_delegator, root_delegatee, root_scope, root_id)
    hop1 = make_hop(depth1_delegator, depth1_delegatee, depth1_scope, depth1_id)
    hops = [hop0, hop1]

    context = source["input"]["context"]
    leaf_preimage = {
        "agent_id": depth1_delegatee,
        "action_type": context["requested_action"],
        "scope": hop1["scope"],
        "timestamp": normalize_timestamp(context["current_time"]),
    }
    chain_artifact = {
        "version": "delegation-chain-ref-v1",
        "chain_id": f"moltycel-aae-v11:{root_id}",
        "hops": [{k: v for k, v in h.items() if k != "source_aae_id"} for h in hops],
        "root_delegator": root_delegator,
        "scope": hop1["scope"],
        "leaf_action_ref": compute_action_ref(leaf_preimage),
    }

    revoked = context["revocation_responses"].get(root_id, {}).get("revoked") is True
    assert revoked, "translation assumes vector 11's root AAE is reported revoked"
    revocation_artifact = {
        "version": "revocation-ref-v1",
        "revoked_action_ref": hop0["delegation_ref"],
        "scope": hop0["scope"],
        "revoked_at": normalize_timestamp(context["current_time"]),  # stand-in, see docstring
        "reason": "aae_revocation_responses_reported_revoked_true",
    }

    return {
        "id": "moltycel-aae-v11-delegation-cascade-revocation",
        "source": {
            "repo": "MoltyCel/aae-conformance-vectors",
            "ref": "22a08d76ef76fda19274a687081523443e2ce7d0",
            "path": "vectors/11-delegation-cascade-revocation.json",
            "source_aae_vector_expected": source["expected"],
        },
        "chain_artifact": chain_artifact,
        "delegation_chain_ref": sha256hex(jcs(chain_artifact)),
        "leaf_preimage": leaf_preimage,
        "revocation_artifact": revocation_artifact,
        "hop_provenance": [
            {"hop_index": i, "source_aae_id": h["source_aae_id"]} for i, h in enumerate(hops)
        ],
    }


def translate_vector_05(source: dict) -> dict:
    """MoltyCel aae-vector-05 (single-use-replay) -> delegation-chain-ref-v1
    chain_artifact + leaf_preimage, plus the replay scenario itself (not a
    field translation -- see run_interop.py).

    Scenario (unchanged from the source vector): enterprise-corp grants a
    root AAE to agent-001 (actions read+book+pay, scope travel-vertical,
    single_use: true). The grant's own id is already present in
    context.consumed_ids -- i.e. this exact presentation has already been
    accepted once before. AAE requires rejecting it.
    """
    token = source["input"]["secured_aae"]
    _, payload = decode_jws(token)
    mandate = mandate_of(payload)

    vc_id = payload["id"]
    delegator = mandate["principal_did"]
    delegatee = payload["credentialSubject"]["id"]
    scope = mandate["scope"]

    assert vc_id in source["input"]["context"]["consumed_ids"], (
        "translation assumes vector 05's own id is already in consumed_ids "
        "-- that is the replay condition being tested"
    )

    hop0 = make_hop(delegator, delegatee, scope, vc_id)
    context = source["input"]["context"]
    leaf_preimage = {
        "agent_id": delegatee,
        "action_type": context["requested_action"],
        "scope": hop0["scope"],
        "timestamp": normalize_timestamp(context["current_time"]),
    }
    chain_artifact = {
        "version": "delegation-chain-ref-v1",
        "chain_id": f"moltycel-aae-v05:{vc_id}",
        "hops": [{k: v for k, v in hop0.items() if k != "source_aae_id"}],
        "root_delegator": delegator,
        "scope": hop0["scope"],
        "leaf_action_ref": compute_action_ref(leaf_preimage),
    }

    return {
        "id": "moltycel-aae-v05-single-use-replay",
        "source": {
            "repo": "MoltyCel/aae-conformance-vectors",
            "ref": "22a08d76ef76fda19274a687081523443e2ce7d0",
            "path": "vectors/05-single-use-replay.json",
            "source_aae_vector_expected": source["expected"],
        },
        "chain_artifact": chain_artifact,
        "delegation_chain_ref": sha256hex(jcs(chain_artifact)),
        "leaf_preimage": leaf_preimage,
        "hop_provenance": [{"hop_index": 0, "source_aae_id": vc_id}],
    }
