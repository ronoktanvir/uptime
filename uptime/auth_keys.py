"""P-256 reviewer credentials. Private JWK files are handled only by offline clients."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def _coordinate(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
        raise ValueError("A canonical P-256 JWK is required")
    raw = base64.urlsafe_b64decode(value + "=")
    if base64.urlsafe_b64encode(raw).decode().rstrip("=") != value:
        raise ValueError("A canonical P-256 JWK is required")
    return int.from_bytes(raw, "big")


def _encode(number):
    return base64.urlsafe_b64encode(number.to_bytes(32, "big")).decode().rstrip("=")


def public_key(credential):
    if not isinstance(credential, dict) or credential.get("kty") != "EC" or credential.get("crv") != "P-256":
        raise ValueError("Use an enrolled P-256 credential file")
    try:
        numbers = ec.EllipticCurvePublicNumbers(_coordinate(credential.get("x")),
                                               _coordinate(credential.get("y")), ec.SECP256R1())
        return numbers.public_key()
    except (ValueError, TypeError):
        raise ValueError("Invalid P-256 public key") from None


def private_key(credential):
    public = public_key(credential)
    try:
        key = ec.derive_private_key(_coordinate(credential.get("d")), ec.SECP256R1())
        if key.public_key().public_numbers() != public.public_numbers():
            raise ValueError("Public and private key differ")
        return key
    except (ValueError, TypeError):
        raise ValueError("Invalid P-256 private credential") from None


def public_bytes(credential):
    key = public_key(credential).public_numbers()
    return json.dumps({"kty":"EC", "crv":"P-256", "x":_encode(key.x), "y":_encode(key.y)},
                      sort_keys=True, separators=(",", ":")).encode()


def _private_jwk(key):
    public = key.public_key().public_numbers()
    return {"kty":"EC", "crv":"P-256", "x":_encode(public.x), "y":_encode(public.y),
            "d":_encode(key.private_numbers().private_value), "ext":True, "key_ops":["sign"]}


def generate_reviewer_key():
    return _private_jwk(ec.generate_private_key(ec.SECP256R1()))


def rehearsal_key(secret):
    """Compatibility for explicit, disposable scripted rehearsal configuration only."""
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("A private rehearsal secret of at least 32 characters is required")
    scalar = int.from_bytes(sha256(b"uptime-scripted-replay-only\0"+secret.encode()).digest(), "big")
    key = _private_jwk(ec.derive_private_key(scalar % (P256_ORDER-1) + 1, ec.SECP256R1()))
    key["uptime_rehearsal"] = True
    return key


def reviewer_signature(credential, message):
    signature = private_key(credential).sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(signature)
    return (r.to_bytes(32, "big")+s.to_bytes(32, "big")).hex()


def verify_reviewer(public, message, proof):
    if not isinstance(proof, str) or not re.fullmatch(r"[a-f0-9]{128}", proof):
        return False
    raw = bytes.fromhex(proof)
    signature = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    try:
        public_key(json.loads(public)).verify(signature, message.encode(), ec.ECDSA(hashes.SHA256()))
        return True
    except (ValueError, InvalidSignature):
        return False


def write_credential(path, credential, repository):
    """Create a private file exclusively at an operator-selected location outside the repo."""
    if not Path(path).is_absolute():
        raise ValueError("Select an absolute credential-file path outside the repository")
    target = Path(path).resolve()
    if target != Path(path):
        raise ValueError("Select a physical credential-file path without symlinks or traversal")
    if target.is_relative_to(Path(repository).resolve()):
        raise ValueError("Store reviewer credentials outside the repository")
    private_key(credential)
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as file:
        json.dump(credential, file, separators=(",", ":"))
        file.write("\n")
    return target
