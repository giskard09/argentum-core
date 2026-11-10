# Record

What third parties have published about this work, and what we have published ourselves. Every line links to a primary source. Nothing here is an endorsement, a certification or a membership claim. For adoption by implementers see [ADOPTERS.md](./ADOPTERS.md).

## 1. Credits in documents written by others

- **draft-dogru-cedulon-core-00** (IETF Internet-Draft, Acknowledgments). "Pablo Etcheverry found that a repeated reference hid the unaccounted amount, ran the suite on a platform its author had not, and found that nothing compared a settlement's clock to the clock of the decision that authorized it." https://datatracker.ietf.org/doc/draft-dogru-cedulon-core/
- **draft-krausz-verification-state-03** (IETF Internet-Draft, Acknowledgments, 1 October 2026). Credits an alternate reading of one finding that is preserved in the document's evidence-pinning rules, and a checker built from the review draft, its amendments and the fixture README, without opening the author's fixture generator or cross-check code, that reproduced all 32 rev7 vectors. The same text notes that this confirmed reproduction from the normative text and was not a from-scratch cold build. https://datatracker.ietf.org/doc/draft-krausz-verification-state/
- **draft-wilder-scitt-physical-site-engage-receipt-02** (IETF Internet-Draft, Acknowledgments). "The author thanks GitHub user giskard09 for a detailed public review" of the -01 adapter and verifier semantics. https://datatracker.ietf.org/doc/draft-wilder-scitt-physical-site-engage-receipt/
- **Comments on the ASG-WG Governance Matrix, Draft Version 2**, Vince Albanese, 9 November 2026, submitted to the ABA Autonomous Systems Governance Working Group. Cites "Mr. Etcheverry's x402 analysis" for the point that a stolen signing key produces an authorization indistinguishable from a legitimate one. https://asg-wg.org/proposed-matrix

## 2. Published by a standards or governance body

- **ABA Autonomous Systems Governance Working Group.** Our written comment of 19 October 2026 on the x402 column of the Draft Matrix is posted with the other submissions. https://asg-wg.org/proposed-matrix
- **IETF.** draft-etcheverry-action-ref, an individual Internet-Draft (not a working group document). https://datatracker.ietf.org/doc/draft-etcheverry-action-ref/

## 3. Work hosted under shared governance

- **Composable Evidence Criteria** (an LF Decentralized Trust lab). Hosts the action-ref conformance Action and its frozen vectors. We are one of its four initial committers; write access is administered by LF Decentralized Trust. https://github.com/Composable-Evidence-Criteria/action-ref-conformance

## 4. Our own work (written and run by us)

- 35 specifications and 49 conformance verifiers in this repository, with public test vectors.
- Worked examples that apply `action_ref` to third-party schemas. Each one is our own example. None implies that the third party integrated, endorsed or took part.
- AnchorRegistry: a permissionless on-chain registry, same address on Base and Arbitrum. No fee beyond network gas.

## Corrections

If a line here overstates what its source says, open an issue. We correct in place and note the change.
