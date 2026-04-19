"""Security helpers for PIN hashing and verification."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Tuple

PBKDF2_ITERATIONS = 120_000
SALT_SIZE = 16


def hash_pin(pin: str) -> Tuple[str, str]:
    """Return a tuple of (salt_hex, pin_hash_hex)."""
    salt = os.urandom(SALT_SIZE)
    pin_hash = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return salt.hex(), pin_hash.hex()


def verify_pin(pin: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Verify a PIN against the stored salt and hash."""
    salt = bytes.fromhex(salt_hex)
    computed_hash = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(computed_hash.hex(), expected_hash_hex)

