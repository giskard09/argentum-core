"""
Minimal BIP-340 (Schnorr over secp256k1) sign/verify, transliterated from the
reference pseudocode in bitcoin/bips#340. No third-party curve library —
this repo's environment has no coincurve/secp256k1 binding installed, and
this artifact is small/one-off enough that pure-Python field arithmetic is
fine (not used for anything performance-sensitive or wallet-custodial).

Deviation from strict BIP-340: `msg` here is the raw JCS preimage bytes,
not a fixed 32-byte hash. BIP-340's own Sign/Verify algorithms never assume
a 32-byte message — the length constraint lives in libsecp256k1's default
`schnorrsig_sign32` entry point, not in the spec's math. Its extended
`schnorrsig_sign_custom` API supports arbitrary-length messages via the
same tagged-hash challenge construction used below. We need the raw
preimage bytes to literally be what's signed (co_suite spec requirement),
so this uses that variable-length form.
"""
import hashlib

P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def _x(pt):
    return pt[0]


def _y(pt):
    return pt[1]


def point_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    if _x(p1) == _x(p2) and _y(p1) != _y(p2):
        return None
    if p1 == p2:
        lam = (3 * _x(p1) * _x(p1) * pow(2 * _y(p1), P - 2, P)) % P
    else:
        lam = ((_y(p2) - _y(p1)) * pow(_x(p2) - _x(p1), P - 2, P)) % P
    x3 = (lam * lam - _x(p1) - _x(p2)) % P
    return (x3, (lam * (_x(p1) - x3) - _y(p1)) % P)


def point_mul(pt, scalar):
    r = None
    for i in range(256):
        if (scalar >> i) & 1:
            r = point_add(r, pt)
        pt = point_add(pt, pt)
    return r


def bytes_from_int(x):
    return x.to_bytes(32, byteorder="big")


def bytes_from_point(pt):
    return bytes_from_int(_x(pt))


def int_from_bytes(b):
    return int.from_bytes(b, byteorder="big")


def xor_bytes(b0, b1):
    return bytes(a ^ b for a, b in zip(b0, b1))


def has_even_y(pt):
    return _y(pt) % 2 == 0


def lift_x(x):
    if x >= P:
        return None
    y_sq = (pow(x, 3, P) + 7) % P
    y = pow(y_sq, (P + 1) // 4, P)
    if pow(y, 2, P) != y_sq:
        return None
    return (x, y if y % 2 == 0 else P - y)


def tagged_hash(tag: str, msg: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + msg).digest()


def pubkey_gen(seckey: bytes) -> bytes:
    d0 = int_from_bytes(seckey)
    if not (1 <= d0 <= N - 1):
        raise ValueError("secret key out of range")
    pt = point_mul(G, d0)
    return bytes_from_point(pt)


def schnorr_sign(msg: bytes, seckey: bytes, aux_rand: bytes) -> bytes:
    d0 = int_from_bytes(seckey)
    if not (1 <= d0 <= N - 1):
        raise ValueError("secret key out of range")
    if len(aux_rand) != 32:
        raise ValueError("aux_rand must be 32 bytes")
    p_pt = point_mul(G, d0)
    d = d0 if has_even_y(p_pt) else N - d0
    t = xor_bytes(bytes_from_int(d), tagged_hash("BIP0340/aux", aux_rand))
    k0 = int_from_bytes(tagged_hash("BIP0340/nonce", t + bytes_from_point(p_pt) + msg)) % N
    if k0 == 0:
        raise RuntimeError("failure. this happens only with negligible probability")
    r_pt = point_mul(G, k0)
    k = k0 if has_even_y(r_pt) else N - k0
    e = int_from_bytes(
        tagged_hash("BIP0340/challenge", bytes_from_point(r_pt) + bytes_from_point(p_pt) + msg)
    ) % N
    sig = bytes_from_point(r_pt) + bytes_from_int((k + e * d) % N)
    if not schnorr_verify(msg, bytes_from_point(p_pt), sig):
        raise RuntimeError("the signature just produced does not verify")
    return sig


def schnorr_verify(msg: bytes, pubkey: bytes, sig: bytes) -> bool:
    if len(pubkey) != 32 or len(sig) != 64:
        return False
    p_pt = lift_x(int_from_bytes(pubkey))
    r = int_from_bytes(sig[0:32])
    s = int_from_bytes(sig[32:64])
    if p_pt is None or r >= P or s >= N:
        return False
    e = int_from_bytes(
        tagged_hash("BIP0340/challenge", sig[0:32] + pubkey + msg)
    ) % N
    r_pt = point_add(point_mul(G, s), point_mul(p_pt, N - e))
    if r_pt is None or not has_even_y(r_pt) or _x(r_pt) != r:
        return False
    return True
