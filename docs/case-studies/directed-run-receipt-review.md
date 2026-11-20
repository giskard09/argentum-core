# Worked example: a verifiability review of a third party's paid receipt

Date: 2026-11-19. Status: directed run, not a client engagement.

This is a worked example of the method behind service 2 in [SERVICES.md](../../SERVICES.md). It is not a delivered service. We chose the artifact, paid for it ourselves and ran the review at our own cost. Our paid service 2 covers only formats that the client itself publishes.

## What we did

We bought one receipt from a public x402 service (1.0 USDC on Base). We then tried to verify it using only what an outside party can obtain: the published spec, the public key list and the revocation list. No credentials, no private access.

## What changed between the two runs

On 17 Nov the receipt could not be closed without a field mapping that we had to assume, because the spec did not say where two signed values came from.

On 19 Nov, after the author published a new release and spec changes, the same receipt closed from the spec text and two published files:

- signature: verified
- response hash: re-derives
- revocation: not revoked

The exact inputs, hashes and results are in the public comment:

https://github.com/x402-foundation/x402/issues/2887#issuecomment-7015170272

The paid response body has this SHA-256:

`892f464acd6fe65133f02d6f5173b3b2ee83e2e074dcfab4febfe0b95fcef474`

## What else we checked

We rewrote the receipt and the revocation list one change at a time (44 cases, with a guard that rejects any mutation that leaves the receipt unchanged).

- Changing any of 8 members of the signed payload read as contradicted.
- The 5 members the spec lists as unbound had no effect.
- In the cases we tried, an unsigned or edited revocation list never read as "not revoked".

## What this does not show

- It is one receipt on one day.
- A valid signature does not attest that the computation behind the response is right.
- It is a reproduction with the author's own verifier, not an independent implementation.
- List monotonicity between fetches was not checked, because we had no earlier list.

## Label

This page is not a certification, endorsement or conformity seal by Rama, by the Composable Evidence Criteria lab or by LFDT.
