# Evidence — ARGENTUM attestation item #002 (testnet prototype)

**Subject**: agentId=3249 (giskard-self) in canonical ERC-8004 IdentityRegistry
on Ethereum Sepolia `0x8004A818BFB912233c491871b3d84c89A494BD9e`

**Attestor**: agentId=3249 (self-attestation for prototype testing only)

**Action**: Registered giskard-self in the canonical cross-chain ERC-8004
IdentityRegistry on Ethereum Sepolia (MOV-8 of the Kleros integration workstream).
Wallet `0xDcc84E9798E8eB1b1b48A31B8f35e5AA7b83DBF4` called `register(string)` with
an agentCard URI; the registry minted a non-transferrable ERC-721 with
`tokenId=3249` and `tokenURI=` the agentCard URL.

**actionHash**: `0x1f57bf575ed0156756fd7788f502f9cd532840e49362f53e271ee0076ed7a5c5`
(keccak256 of
`"MOV-8 register canonical agentId=3249 tx=0xe418a230874bb30069381d8f5981c0db52632514aa413c75f896147d8793f534"`)

## Supporting facts

- Register tx on Eth Sepolia:
  `0xe418a230874bb30069381d8f5981c0db52632514aa413c75f896147d8793f534`
- Registry (canonical, CREATE2): `0x8004A818BFB912233c491871b3d84c89A494BD9e`
- Agent token: `tokenId=3249`, owner `0xDcc84E9798E8eB1b1b48A31B8f35e5AA7b83DBF4`
- agentCard:
  `https://raw.githubusercontent.com/giskard09/giskard-payments/main/agentcards/giskard-self-sepolia-canonical.json`
- Linked existing deploys: GiskardIdentityRegistry (Arb One)
  `0x1C56Ee3cd533C3c8Ac1E87870d43dDF8eC1F9CF3` — PATH B dual-registry design.

## Purpose of this item

Exercise the Publisher Relay flow: this Curate v2 devnet instance
(`0xbd03105eb9dce82a9a8b7e2564bb7d2572998e3d` on Arbitrum Sepolia devnet) is
being used as the source of truth for an attestation about agentId=3249 on the
canonical Ethereum Sepolia ReputationRegistry. Monitoring will determine whether
the Publisher Relay (`0xb9080458de79f614db5d5208ab31bbf22a33dead`) picks this
item up and emits a `FeedbackSubmitted` event on
`0x8004B663056A597Dffe9eCcC1965A193B7388713` referencing
`subjectAgentId=3249`.

## Notes

Testnet-only prototype. Not economically consequential. Self-attestation is used
only because the prototype needs one attestor; production attestations will be
peer-issued.
