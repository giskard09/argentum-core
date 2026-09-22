# recipient-allocation-ref-v1 — Specification

**Stable tag:** `recipient-allocation-ref-v1.0`
**Status:** stable
**Canonical fixture:** [`examples/conformance/recipient-allocation-ref/`](../../examples/conformance/recipient-allocation-ref/)

---

## What is recipient-allocation-ref

`recipient_allocation_ref` is a SHA-256 hex commitment to the full per-recipient
allocation at the moment a multi-recipient payment action was authorized. It extends
`recipient_set_hash` — which only proves the set of addresses was not substituted —
by also committing the amount assigned to each address.

**The gap `recipient_set_hash` does not cover:**

A verifier holding only `recipient_set_hash` can confirm no address was added or
removed. It cannot detect a redistribution of amounts among the same set: same
aggregate, same recipients, different per-recipient values. This is an
ALLOCATION_REDISTRIBUTION failure that `recipient_set_hash` passes silently.

`recipient_allocation_ref` closes this gap: any change to a per-recipient amount,
to the aggregate, or to the currency produces a distinct hash.

---

## Preimage schema

```json
{
  "aggregate_usdc":         "<string — total USDC in base units (wei)>",
  "currency":               "<string — token symbol, e.g. USDC>",
  "recipient_allocations":  [
    { "address": "<checksummed EVM address>", "amount_usdc": "<string — base units>" }
  ],
  "timestamp_ms":           <integer — Unix epoch milliseconds at authorization time>
}
```

**Ordering:** `recipient_allocations` MUST be sorted lexicographically by `address`
(ascending, case-insensitive normalization applied before sort). JCS sorts object
keys alphabetically — the array order is explicit and significant.

**Types:** `aggregate_usdc` and `amount_usdc` are strings, not integers, to avoid
floating-point precision loss across runtimes. `timestamp_ms` is an integer.

Field order in each allocation object is irrelevant — JCS canonicalization
normalizes it.

---

## Derivation

```
recipient_allocation_ref = SHA-256(JCS(preimage))
```

JCS: RFC 8785 canonical JSON: object keys sorted recursively by UTF-16 code units (§3.2.3), no whitespace, literal UTF-8 — **not** `json.dumps(sort_keys=True)`, which sorts by code point and diverges for keys outside the BMP. Reference implementation: [`jcs.py`](../../jcs.py).

```python
import hashlib, json

def jcs(obj):
    # RFC 8785 §3.2.3: object keys sorted recursively by UTF-16 code units.
    # Not json.dumps(sort_keys=True): that sorts by code point and diverges
    # from RFC 8785 for keys outside the BMP. Floats additionally need
    # ECMA-262 Number::toString formatting -- see jcs.py.
    def canon(o):
        if isinstance(o, dict):
            return {k: canon(o[k]) for k in sorted(o, key=lambda k: k.encode("utf-16-be", "surrogatepass"))}
        if isinstance(o, list):
            return [canon(v) for v in o]
        return o
    return json.dumps(canon(obj), separators=(',', ':'), ensure_ascii=False)

preimage = {
    "aggregate_usdc": "3000000",
    "currency": "USDC",
    "recipient_allocations": [
        {"address": "0xaaa0000000000000000000000000000000000001", "amount_usdc": "1000000"},
        {"address": "0xbbb0000000000000000000000000000000000002", "amount_usdc": "1500000"},
        {"address": "0xccc0000000000000000000000000000000000003", "amount_usdc": "500000"}
    ],
    "timestamp_ms": 1750953600000
}

recipient_allocation_ref = hashlib.sha256(jcs(preimage).encode()).hexdigest()
# a774a2a065e7bf0e94f217c3946695bc4db89dafc559193329222213d7f21b08
```

---

## Usage in TrailRecord

`recipient_allocation_ref` is an optional field in `TrailRecord`. When present,
it asserts that the per-recipient allocation was committed at authorization time
and has not been redistributed before execution.

```json
{
  "action_type":               "basepay:transfer.batch",
  "agent_id":                  "basepay-agentkit",
  "recipient_allocation_ref":  "<sha256 hex>",
  "scope":                     "basepay:permit_batch_pay_usdc"
}
```

A verifier who holds the preimage can recompute the ref and confirm the executed
calldata matches the committed allocations.

---

## Failure mode: ALLOCATION_REDISTRIBUTION

An ALLOCATION_REDISTRIBUTION failure occurs when:

- `aggregate_usdc` is unchanged
- the address set is unchanged (passes `recipient_set_hash`)
- at least one per-recipient `amount_usdc` differs from the committed value

The `recipient_allocation_ref` computed from the executed calldata will not match
the committed ref. A conformant verifier MUST reject.

This failure mode is undetectable by `recipient_set_hash` alone — it requires
`recipient_allocation_ref` to be carried in the trail.

---

## Relationship to other primitives

| Primitive | What it commits |
|-----------|----------------|
| `recipient_set_hash` | address set — detects substitution, not redistribution |
| `recipient_allocation_ref` | address set + per-recipient amounts — detects both |
| `action_ref` | full action envelope (action_type, agent_id, scope, timestamp) |

`recipient_allocation_ref` and `recipient_set_hash` are complementary: a trail
may carry both. `recipient_set_hash` is cheaper to verify (no amount data required);
`recipient_allocation_ref` is the stronger commitment when amount integrity matters.
