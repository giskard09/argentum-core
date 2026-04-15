# ARGENTUM Attestations — Acceptance Policy (Testnet Prototype)

This is a **testnet-only prototype** list for evaluating Kleros Curate v2 as
a dispute layer for ERC-8004 agent attestations. Items on this list are
illustrative and not economically consequential.

## Scope

An item represents an **attestation**: agent A (attestor) vouches that agent B
(subject, `agentId`) performed a specific action identified by `actionHash`.

## Acceptance criteria

An attestation is **valid** (jurors vote "accept") if all hold:

1. `agentId` resolves to a real entry in `GiskardIdentityRegistry`
   at `0x1C56Ee3cd533C3c8Ac1E87870d43dDF8eC1F9CF3` (Arbitrum One).
2. `actionHash` is reproducible from the evidence at `evidenceURI`
   (i.e. `keccak256` of the canonical action description matches).
3. `evidenceURI` resolves to a publicly accessible resource.
4. The attestor agentId is itself a valid entry in the registry.
5. The content at `evidenceURI` is consistent with the action claimed —
   no misrepresentation, no doctored evidence.

An attestation is **invalid** (jurors vote "reject") if any of the above fails,
or if the claim is materially misleading.

## Notes for jurors

- This is a prototype. In production, attestations carry economic weight
  (karma/ARGT). On testnet, the purpose is only to validate the flow.
- When in doubt, prefer rejection — the cost of a false positive in a
  reputation system is higher than the cost of a false negative.

## Out of scope

- Opinions about whether the action itself was "good" or "bad". Attestations
  only assert that the action *happened* as described.
- Jurisdictional legality of the action. Separate question, separate system.
