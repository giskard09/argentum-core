"""
Independent verifier for cell.json — recomputes preimage_jcs from the raw
preimage dict (not the stored string) and checks the BIP-340 signature.
Also runs the R3 drop-one-signature negative: strip the signature, confirm
verification fails, confirm the authority_ref string is still present in
the preimage bytes verbatim (the co-suite invariant kenneives asked for).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bip340
from generate import jcs, AUTHORITY_REF


def main():
    cell_path = os.path.join(os.path.dirname(__file__), "cell.json")
    with open(cell_path) as f:
        cell = json.load(f)

    preimage = cell["preimage"]
    recomputed_jcs = jcs(preimage)
    assert recomputed_jcs.decode("utf-8") == cell["preimage_jcs"], "JCS(preimage) does not match stored preimage_jcs"

    pubkey = bytes.fromhex(cell["signature"]["pubkey_x_only"])
    sig = bytes.fromhex(cell["signature"]["sig"])

    valid = bip340.schnorr_verify(recomputed_jcs, pubkey, sig)
    print(f"valid signature over recomputed preimage: {valid}")
    assert valid

    assert preimage["authority_ref"] == AUTHORITY_REF
    assert AUTHORITY_REF.encode("utf-8") in recomputed_jcs, "authority_ref not verbatim in signed bytes"
    print("authority_ref present verbatim in signed bytes: True")

    # R3 negative: corrupt the signature (stand-in for "drop leg A's signature") — must fail.
    corrupted_sig = bytearray(sig)
    corrupted_sig[0] ^= 1
    dropped_ok = bip340.schnorr_verify(recomputed_jcs, pubkey, bytes(corrupted_sig))
    print(f"drop-one-signature negative correctly FAILS: {not dropped_ok}")
    assert not dropped_ok

    # R3 negative: tamper the authority_ref value itself — must fail against the original signature.
    tampered_preimage = dict(preimage)
    tampered_preimage["authority_ref"] = "v2:0000000000000000000000000000000000000000000000000000000000000000"
    tampered_ok = bip340.schnorr_verify(jcs(tampered_preimage), pubkey, sig)
    print(f"tampered authority_ref correctly FAILS original signature: {not tampered_ok}")
    assert not tampered_ok

    print("ALL CHECKS PASS")


if __name__ == "__main__":
    main()
