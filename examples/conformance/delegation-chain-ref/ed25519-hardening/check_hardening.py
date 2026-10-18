"""
Regression check: does this repo's pinned Ed25519 verification library
(PyNaCl, see ../requirements.txt) still reject the known classes of
Ed25519 signature-verification edge cases it is expected to reject?

Built 2026-10-18, preventive, no external trigger: robertolocatelli81-dev/
Noûs found, the same day and unrelated to this repo, that identity-element
keys (R=identity, S=0) forge a valid-looking signature for ANY message
under naive RFC 8032 verification, and that non-canonical point/scalar
encodings (ed25519-speccheck classes 0 and 11) are accepted by some
libraries (x402-foundation/tsc#4). This repo's only LIVE (not
declared/external) Ed25519 verification is `hop_signature` in
delegation-chain-ref.md, via PyNaCl -- everywhere else (peer-reconciliation
-ref-v1's co_signer, anchoring-precedence-ref-v1's admission_invariant)
signature validity is a declared, externally-resolved fact, not computed by
this repo's own code. This check closes the "not verified explicit" gap:
it does not assume PyNaCl/libsodium happens to be strict, it reproduces the
real published test vectors against the real pinned library in this repo's
own environment and checks the result matches the documented LibSodium
behavior.

Source (vendored verbatim, Apache-2.0): `novifinancial/ed25519-speccheck`,
commit `65519336fda78a3d016e947df6d82848aca0c9da`. `cases.json` in this
directory is byte-identical to that commit's file (verified via
`git hash-object`, matches the GitHub API's blob sha
8686dcb7eef8b6abe36ca8fa9bb10de112e63774 for the same path at that commit).
The expected LibSodium column below is transcribed from that commit's
`results.md` condition table -- this script does not re-derive it, it
checks our own library against it.

  case | condition                                          | expected (LibSodium)
  -----|-----------------------------------------------------|---------------------
    0  | S=0, small-order A, small-order R (universal forgery)       | reject
    1  | small-order A only, 0<S<L                                   | reject
    2  | small-order R only, 0<S<L                                   | reject
    3  | mixed-order A and R, 0<S<L (benign; not a vulnerability)    | ACCEPT
    4  | mixed A/R, fails cofactorless verification                 | reject
    5  | pre-reduced scalar, R has order L                           | reject
    6  | S out of bounds (S > L)                                    | reject
    7  | S out of bounds (S >> L, no canonical serialization)       | reject
    8  | non-canonical R, reduced for hash                          | reject
    9  | non-canonical R, not reduced for hash                      | reject
   10  | non-canonical A, reduced for hash                          | reject
   11  | non-canonical A, not reduced for hash                      | reject

Case 3 is the only expected ACCEPT -- it is not malformed in any of the
ways the other 11 cases are, and every library in results.md's table
accepts it except the two that also reject 0/1/2 (LibSodium, libra-crypto)
plus "Dalek strict". A check that expects all 12 to reject would be
checking for behavior PyNaCl does not (and should not) have.

Usage: python3 check_hardening.py  (needs PyNaCl; pip install -r ../requirements.txt)
"""

import binascii
import json
import sys
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

EXPECTED_LIBSODIUM_ACCEPTS = {3}  # every other case (0,1,2,4-11) must reject


def main():
    cases_path = Path(__file__).parent / "novifinancial-ed25519-speccheck-cases.json"
    cases = json.loads(cases_path.read_text())

    print(f"ed25519 hardening check — {len(cases)} vectors "
          f"(novifinancial/ed25519-speccheck @ 65519336)\n")

    passed = 0
    failed = 0
    for i, case in enumerate(cases):
        msg = binascii.unhexlify(case["message"])
        pub = binascii.unhexlify(case["pub_key"])
        sig = binascii.unhexlify(case["signature"])

        try:
            VerifyKey(pub).verify(msg, sig)
            accepted = True
        except BadSignatureError:
            accepted = False

        should_accept = i in EXPECTED_LIBSODIUM_ACCEPTS
        ok = accepted == should_accept
        marker = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"
        print(f"  {marker} [{status}] case {i:2d}: "
              f"{'accepted' if accepted else 'rejected'} "
              f"(expected {'accept' if should_accept else 'reject'})")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{len(cases)} passed", end="")
    if failed:
        print(f", {failed} failed -- our pinned PyNaCl/libsodium no longer "
              f"matches the documented hardening. Do not treat delegation-chain-ref's "
              f"hop_signature check as protected against these classes until this is "
              f"investigated.")
        sys.exit(1)
    else:
        print(" -- matches documented LibSodium behavior exactly.")


if __name__ == "__main__":
    main()
