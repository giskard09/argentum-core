# action_ref as an x402 `action-receipt` binding

**Status:** written against draft 0.4 of [`jsuich/x402-action-receipt`](https://github.com/jsuich/x402-action-receipt), pull request [#2](https://github.com/jsuich/x402-action-receipt/pull/2), head `a7a316677760f862454f7f27bd10ebafafe634d1`, file `action-receipt.md`. Re-checked when that pull request is merged; until then, read this against that draft and not against a later one.

**Credit.** The carriage rules are Josh Suich's (jsuich), draft 0.4 §4.5. This document only defines one binding type under those rules.

**Claim limits.** This document does not imply that jsuich, `x402-action-receipt` or the x402 Foundation adopted, reviewed or endorsed it. It does not claim that the verifier in that repository supports the type defined here (see [Example](#example), where it does not evaluate it).

This is a follow-up to a public comment of 2026-07-20 on x402 issue 2906: [x402-foundation/x402#2906 (comment)](https://github.com/x402-foundation/x402/issues/2906#issuecomment-5024785590). It takes a different form from the one described there: a document that defines a binding type, not a profile section of another document.

---

## What is defined

One binding `type`, and the form of its `value`.

```
type  = https://github.com/giskard09/argentum-core/blob/main/docs/spec/action-ref-x402-binding.md
value = an action_ref string, exactly as action-ref.md writes it
```

Draft 0.4 §4.5 gives a `type` the form `prefix ":" name`. Checked for the string above: the prefix is `https` (5 characters, lowercase letters only, within the 1 to 64 limit and the grammar `[a-z][a-z0-9+.-]*`), and the name is `//github.com/giskard09/argentum-core/blob/main/docs/spec/action-ref-x402-binding.md`, 83 printable ASCII characters (0x21 to 0x7E), within the 1 to 191 limit. Under §4.5.1 the prefix is not an x402 extension key, so the `type` is a URI defined by whoever controls it; here, that is this file.

## The value

`value` is the `action_ref` string verbatim, as [action-ref.md](action-ref.md) defines it. It is not re-encoded, re-hashed or prefixed by the binding.

| Version | Form | Length |
|---|---|---|
| v1 | 64 lowercase hexadecimal characters, no prefix | 64 |
| v2 | `v2:` followed by 64 lowercase hexadecimal characters | 67 |

The version is read from the string itself, as in [Version negotiation](action-ref.md#version-negotiation) of action-ref.md. Both forms are printable ASCII and inside the 1 to 1024 limit of §4.5.

## Placement among other bindings

Draft 0.4 §4.5 requires the array to be in strictly ascending ASCII order of `type`, at most 16 entries, one per `type`. This `type` begins with `https:`. In ASCII it sorts after `action-receipt:` and before `offer-receipt:` and `response-provenance:` (`a` < `h` < `o` < `r`). Against another URI type, compare the strings byte by byte.

## How a third party checks it

The binding carries only the digest. To check it, the verifier needs the four preimage fields from somewhere else.

1. Obtain `agent_id`, `action_type`, `scope` and `timestamp` from the party or record that holds them.
2. Read the version from the `value` (bare hexadecimal is v1, `v2:` is v2).
3. Recompute `action_ref` as [action-ref.md](action-ref.md) defines it for that version.
4. Compare with the `value`. Equal: the digest matches those four fields. Different: it does not.

Three differences between an `action-receipt` and an `action_ref` preimage, read from the two documents. None is resolved here; each decides whether a given receipt can carry a computable `action_ref`.

- The receipt's `action.scope` may be empty (§4.2). `action_ref` rejects an empty `scope` before hashing. A receipt with an empty `scope` cannot carry a digest that a third party can recompute from that receipt's own members.
- `action_ref` accepts only ASCII in `agent_id`, `action_type` and `scope`. The receipt's `agent`, `actionType` and `scope` are opaque strings with no such limit (§4.2).
- The receipt carries `issuedAt` as integer Unix seconds (§4.1). The preimage `timestamp` is an RFC 3339 UTC string with three millisecond digits. The receipt has no member that is the preimage `timestamp`.

Which receipt member, if any, a deployment uses for each preimage field is the deployment's choice. This document does not assert a mapping.

## What it proves, and what it does not

The receipt's signature gives the binding carriage (§4.5.1): the signer committed to that `value`, in that receipt, for that settlement. Whether the value is true is decided by the owning specification's own procedure, which here is the recomputation above.

Recomputing proves that the four fields you hold hash to the carried digest. That the signer committed to this value, in this receipt, is what the receipt's signature gives, and it has to be verified separately. Recomputing does not prove that those fields correspond to what the agent's runtime did, that the signer populated them honestly, or that the action was authorized. The same boundary is stated in [Boundary](action-ref.md#boundary--what-this-proves-and-what-it-does-not) of action-ref.md. The binding does not change a receipt's verdict (§4.5.1), and `action_ref` is not `receiptRef`: draft 0.4 §11 states they are not interchangeable.

## Example

Synthetic, built with the helpers and test keys of the draft 0.4 repository (its committed `vectors/keys.json`, `did:web:api.example.com#ed25519`, EdDSA). The values `did:web:agent.example`, `inference.completion` and `read:model-x` are that repository's fixture values; the timestamp is invented.

Preimage fields: `agent_id` = `did:web:agent.example`, `action_type` = `inference.completion`, `scope` = `read:model-x`, `timestamp` = `2026-11-21T12:00:00.000Z`.

- v1: `09d492c7232f02a0d912452aa4df971bc24a67f6666566a26db7aa62d227644b`
- v2: `v2:91f87a186f087c36dbad0eccaa6cea207d473e2df910909c98768d7a5c3ee6a1`

Both were computed from the text of action-ref.md and checked equal to `compute_action_ref` and `compute_action_ref_v2` in `plugins/agt_evidence_anchor/action_ref.py`.

Receipt payload (v1 binding; JWS header `{"alg":"EdDSA","kid":"did:web:api.example.com#ed25519","typ":"x402-action-receipt+jws"}`):

```json
{
  "action": {"actionType": "inference.completion", "agent": "did:web:agent.example", "outcome": "delivered", "scope": "read:model-x"},
  "bindings": [
    {"type": "https://github.com/giskard09/argentum-core/blob/main/docs/spec/action-ref-x402-binding.md",
     "value": "09d492c7232f02a0d912452aa4df971bc24a67f6666566a26db7aa62d227644b"}
  ],
  "chargedAmount": "10000",
  "issuedAt": 1703123456,
  "network": "eip155:8453",
  "payTo": "0x209693bc6afc0c5328ba36faf03c514ef312287c",
  "payer": "0x857b06519e91e3a54538791bdbb0e22373e36b66",
  "receiptId": "Zm9yLXRlc3Rpbmctb25seS0wMQ",
  "requirementsDigest": "sha256:928ef8ee5f5df7a325dc5a5e2dbd9a3cdf89ab71fe28dec7c713e6efdd36aabc",
  "resourceUrl": "https://api.example.com/v1/complete",
  "settlementRef": "",
  "settlementStatus": "settled",
  "supersedes": "",
  "transaction": "0xabababababababababababababababababababababababababababababababab",
  "version": 1
}
```

Compact JWS, as the `signature` member of `{"format": "jws", "signature": ...}`:

```
eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDp3ZWI6YXBpLmV4YW1wbGUuY29tI2VkMjU1MTkiLCJ0eXAiOiJ4NDAyLWFjdGlvbi1yZWNlaXB0K2p3cyJ9.eyJhY3Rpb24iOnsiYWN0aW9uVHlwZSI6ImluZmVyZW5jZS5jb21wbGV0aW9uIiwiYWdlbnQiOiJkaWQ6d2ViOmFnZW50LmV4YW1wbGUiLCJvdXRjb21lIjoiZGVsaXZlcmVkIiwic2NvcGUiOiJyZWFkOm1vZGVsLXgifSwiYmluZGluZ3MiOlt7InR5cGUiOiJodHRwczovL2dpdGh1Yi5jb20vZ2lza2FyZDA5L2FyZ2VudHVtLWNvcmUvYmxvYi9tYWluL2RvY3Mvc3BlYy9hY3Rpb24tcmVmLXg0MDItYmluZGluZy5tZCIsInZhbHVlIjoiMDlkNDkyYzcyMzJmMDJhMGQ5MTI0NTJhYTRkZjk3MWJjMjRhNjdmNjY2NjU2NmEyNmRiN2FhNjJkMjI3NjQ0YiJ9XSwiY2hhcmdlZEFtb3VudCI6IjEwMDAwIiwiaXNzdWVkQXQiOjE3MDMxMjM0NTYsIm5ldHdvcmsiOiJlaXAxNTU6ODQ1MyIsInBheVRvIjoiMHgyMDk2OTNiYzZhZmMwYzUzMjhiYTM2ZmFmMDNjNTE0ZWYzMTIyODdjIiwicGF5ZXIiOiIweDg1N2IwNjUxOWU5MWUzYTU0NTM4NzkxYmRiYjBlMjIzNzNlMzZiNjYiLCJyZWNlaXB0SWQiOiJabTl5TFhSbGMzUnBibWN0YjI1c2VTMHdNUSIsInJlcXVpcmVtZW50c0RpZ2VzdCI6InNoYTI1Njo5MjhlZjhlZTVmNWRmN2EzMjVkYzVhNWUyZGJkOWEzY2RmODlhYjcxZmUyOGRlYzdjNzEzZTZlZmRkMzZhYWJjIiwicmVzb3VyY2VVcmwiOiJodHRwczovL2FwaS5leGFtcGxlLmNvbS92MS9jb21wbGV0ZSIsInNldHRsZW1lbnRSZWYiOiIiLCJzZXR0bGVtZW50U3RhdHVzIjoic2V0dGxlZCIsInN1cGVyc2VkZXMiOiIiLCJ0cmFuc2FjdGlvbiI6IjB4YWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYiIsInZlcnNpb24iOjF9.C5__3fNaLaFifz-pPOEwm_7nD8GZuLALKV4kL-U1awpH8LKfaxr8fcU93u2-OcXZvpLoQMqP23PxDw1ML9ggDA
```

What the draft 0.4 verifier did with it. Run on 2026-11-22 (UTC) in an empty clone at `a7a316677760f862454f7f27bd10ebafafe634d1`, as `python3 -I action_receipt.py --verify <file>` with the file path as an argument, Python 3.12 and `cryptography` 41.0.7 (its `requirements.txt` pins 50.0.2; `rfc8785` was not installed, so the optional cross-check was off). No network sandbox was available; the module imports no network library.

| Receipt | Result |
|---|---|
| v1 binding (above) | `PASS`; the binding is reported `not_evaluated`; the receipt is not rejected |
| same, v2 binding | `PASS`; `not_evaluated` |
| same, `value` replaced by 64 zeros | `PASS`; `not_evaluated` |
| the `action-receipt:advertised-info` binding first, ours second | `PASS`; both `not_evaluated` |
| ours before `action-receipt:advertised-info` (not ascending) | `REJECT invalid_actionreceipt_binding` |
| `type` = `action-receipt:action-ref` (closed namespace) | `REJECT invalid_actionreceipt_binding` |
| our `type` followed by a space | `REJECT invalid_actionreceipt_binding` |

Two reading notes. First, that verifier does not evaluate this type: a wrong `value` gives the same result as the right one, so a `PASS` from it says nothing about the `action_ref`. The recomputation above has to be run separately. Second, the three rejections show the binding grammar is checked on the receipt, so `not_evaluated` is not the result of the bindings not being read.

## Limits

- Draft 0.4 may change before it is merged or after. This document follows 0.4 only, and is re-checked on merge.
- The verifier in that repository does not implement this type (see above). No other verifier is claimed to.
- The `type` is a URL of a file in this repository. It has to keep resolving. If the file moves, the `type` string stays the same and may stop resolving; a new `type` would then be needed.
- There is no registry of binding types: under draft 0.4 §4.5.1, a URI type is defined by whoever controls the URI, and the meaning is whatever that owner's text said when the receipt was issued.
- A receipt with an empty `scope`, a non-ASCII `agent`, `actionType` or `scope`, or no source for the preimage `timestamp`, cannot carry a recomputable `action_ref` (see [How a third party checks it](#how-a-third-party-checks-it)).
- The example is one synthetic receipt, signed with the draft repository's test key. It says nothing about a deployment.
