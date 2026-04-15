# Evidence — ARGENTUM attestation item #001 (testnet prototype)

**Subject**: agentId=1 (Giskard-self) in GiskardIdentityRegistry on Arbitrum One
`0x1C56Ee3cd533C3c8Ac1E87870d43dDF8eC1F9CF3`

**Attestor**: agentId=1 (self-attestation for prototype testing only)

**Action**: Deployed GiskardIdentityRegistry (ERC-8004 compliant) to Arbitrum One
on 2026-04-14 with 17 Foundry tests passing and Sourcify verification.

**actionHash**: `0x8b1a9953c4611296a827abf8c47804d7e0f06b3d9f7f8a5b2e4d6c8a0b1c2d3e`
(mock hash for testnet — in production this would be keccak256 of a canonical
action description).

## Supporting facts

- Deploy tx on Arbitrum One:
  `0x3fab9cf4eb27e4f27d78cb1f52a95e8e82e9b802252f38dd88042edc8f6c4fb6`
- Contract: `0x1C56Ee3cd533C3c8Ac1E87870d43dDF8eC1F9CF3`
- Sourcify: exact_match
- Tests: `test/IdentityRegistry.t.sol` — 17 passed, 0 failed
- Repo: github.com/giskard09/giskard-payments

## Notes

This is a **testnet-only prototype** attestation exercised as part of
MOV-1 in the Kleros integration workstream. Not economically consequential.
