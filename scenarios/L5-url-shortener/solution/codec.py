"""
codec.py — URL code generation for the URL shortener service.

A-2 Resolution: Fixed length 6, base62 alphabet [0-9A-Za-z]{6}.
Each generated code is exactly 6 characters drawn from the 62-character
alphabet consisting of digits (0-9), uppercase letters (A-Z), and
lowercase letters (a-z). This gives 62^6 = 56,800,235,584 possible codes.
"""

import random

# Base62 alphabet: digits, uppercase, lowercase
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CODE_LENGTH = 6

# Reserved path segments that must never be returned as a short code
RESERVED = frozenset({
    "health",
    "api",
    "docs",
    "redoc",
    "openapi.json",
    "favicon.ico",
    "",
})


def generate_code(rng: random.Random) -> str:
    """
    Draw CODE_LENGTH random characters from ALPHABET and return the result.

    If the drawn code equals a reserved segment, redraw (loop) until a
    non-reserved code is produced.

    Args:
        rng: A random.Random instance to use for character selection.

    Returns:
        A 6-character string from [0-9A-Za-z] that is not a reserved segment.
    """
    while True:
        code = "".join(rng.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if code not in RESERVED:
            return code
