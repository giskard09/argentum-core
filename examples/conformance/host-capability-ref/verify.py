"""Reference verifier for host-capability-ref: what a verifier reports when the host
running it lacks an algorithm the artifact's profile allows.

A missing capability is a property of the host, not of the artifact. It is not a bad
signature (verify-failure-mode-ref's verify_invalid means the evidence was actively
contradicted), so a host without the algorithm reports NOT_ASSESSED with reason
capability_unavailable:<scheme>. It never turns an adverse finding the host could make
without that capability into NOT_ASSESSED: a preimage that does not match its declared
canonical bytes is FAIL on every host.

Every vector declares:
  expected          verdicts a conformant verifier may return on some host
  expected_by_host  what this reference verifier returns with and without the capability

    python3 verify.py    # scores every vector on both hosts; exit 0 iff all match
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "host_capability_bip340", HERE.parent / "composed-attestation-bip340-cell" / "bip340.py")
bip340 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bip340)

SCHEME = "bip340-schnorr-secp256k1"
HOSTS = {"capable": {SCHEME}, "incapable": set()}


def jcs(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def schnorr_verify(msg: bytes, pubkey: bytes, sig: bytes) -> bool:
    return bip340.schnorr_verify(msg, pubkey, sig)


def evaluate(artifact: dict, capabilities: set) -> tuple[str, list[str], list[str]]:
    """Returns (verdict, failures, not_assessed); FAIL outranks NOT_ASSESSED outranks PASS."""
    failures, not_assessed = [], []
    recomputed = jcs(artifact["preimage"])
    if recomputed.decode("utf-8") != artifact["preimage_jcs"]:
        failures.append("preimage_jcs_mismatch: JCS(preimage) differs from the declared "
                        "preimage_jcs (checked without any signature capability)")
    scheme = artifact["signature"]["scheme"]
    if scheme not in capabilities:
        not_assessed.append(f"capability_unavailable:{scheme}: this host cannot verify the signature")
    elif not schnorr_verify(recomputed, bytes.fromhex(artifact["signature"]["pubkey_x_only"]),
                            bytes.fromhex(artifact["signature"]["sig"])):
        failures.append("signature_invalid: the signature does not verify over JCS(preimage)")
    if failures:
        return "FAIL", failures, not_assessed
    if not_assessed:
        return "NOT_ASSESSED", failures, not_assessed
    return "PASS", failures, not_assessed


def score(v: dict, host: str, verdict: str, failures: list[str]) -> bool:
    if verdict != v["expected_by_host"][host] or verdict not in v["expected"]:
        return False
    if verdict == "FAIL" and v.get("failure_mode"):
        return any(f.startswith(v["failure_mode"]) for f in failures)
    return True


def run() -> list[tuple[str, str, str, bool]]:
    data = json.loads((HERE / "vectors.json").read_text())
    results = []
    for v in data["vectors"]:
        consistent = set(v["expected_by_host"].values()) <= set(v["expected"])
        for host, caps in HOSTS.items():
            verdict, failures, _ = evaluate(v["artifact"], caps)
            results.append((v["id"], host, verdict, consistent and score(v, host, verdict, failures)))
    return results


def main() -> int:
    results = run()
    for vid, host, verdict, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {vid:42s} host={host:9s} -> {verdict}")
    bad = [r for r in results if not r[3]]
    print(f"\n{len(results) - len(bad)}/{len(results)} scored as declared")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
