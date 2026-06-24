# restraint-receipt-v1

## Core Invariant

A terminal receipt (denied/deferred) cannot be interpreted independently from the verifier surface that made the pre-execution decision. Denied and deferred outcomes are useful only if the record also fixes which verifier and which policy bundle produced that decision.

## Vector Coverage

| ID | Verdict | Failure Mode |
|----|---------|--------------|
| RR-ACCEPT-001 | ✅ | Denied — all required fields |
| RR-ACCEPT-002 | ✅ | Deferred — all required fields |
| RR-ACCEPT-003 | ✅ | Denied + full audit_checkpoints |
| RR-REJECT-001 | ❌ | Missing decision_id |
| RR-REJECT-002 | ❌ | Missing policy_bundle in audit_checkpoints |
| RR-REJECT-003 | ❌ | Empty audit_checkpoints |
| RR-REJECT-004 | ❌ | audit_checkpoints not in canonical preimage |
| RR-REJECT-005 | ❌ | policy_bundle digest mismatch |
| RR-REJECT-006 | ❌ | Verifier identity not matching decision record |

## Failure Modes

### 1. Field Completeness (RR-REJECT-001, RR-REJECT-003)
Required fields must be present and non-empty. An empty `audit_checkpoints` object signals presence without substance.

### 2. Canonical Inclusion (RR-REJECT-002, RR-REJECT-004)
Every field in the submitted receipt must be present in the canonical preimage. A field that appears only in the submitted receipt indicates quiet-drift.

### 3. Content-Address Verification (RR-REJECT-005, RR-REJECT-006)
When audit_checkpoints are present, both `verifier` and `policy_bundle` must match the canonical preimage. A digest mismatch or unexpected verifier identity invalidates the receipt.
