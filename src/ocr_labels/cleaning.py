"""Normalization and validation of OCR-read codes.

OCR engines frequently confuse letters and digits (O/0, I/1, S/5...).
These functions correct those confusions and allow incorrect readings to
be discarded using the SSCC check digit (GS1 modulo 10).
"""

from __future__ import annotations

# Map of characters that OCR commonly confuses with digits.
REPLACEMENTS: dict[str, str] = {
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "I": "1", "l": "1", "i": "1", "|": "1", "!": "1",
    "Z": "2", "z": "2",
    "S": "5", "s": "5",
    "G": "6",
    "B": "8",
    "A": "4", "a": "4",
    "T": "7",
}

CODE_LENGTH = 18


def clean_code(text: str, preserved_prefix_length: int = 4) -> str:
    """Replace letters with the digits they are commonly confused with.

    The first ``preserved_prefix_length`` characters are left unchanged because
    the code prefix is known and has already been validated by the regular
    expression.

    >>> clean_code("4260OI2345678901Z5")
    '426001234567890125'
    """
    prefix = text[:preserved_prefix_length]
    remainder = text[preserved_prefix_length:]
    for letter, digit in REPLACEMENTS.items():
        remainder = remainder.replace(letter, digit)
    return prefix + remainder


def is_valid_code(code: str) -> bool:
    """Check that the code is numeric and has the expected length."""
    return code.isdigit() and len(code) == CODE_LENGTH


def sscc_check_digit(code: str) -> int:
    """Calculate the GS1 check digit (modulo 10) of an SSCC.

    Accepts either the complete code or its first 17 digits.
    """
    base = code[:17]
    if len(base) != 17 or not base.isdigit():
        raise ValueError("17 digits are required to calculate the check digit")
    total = sum(int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(base))
    return (10 - total % 10) % 10


def is_valid_sscc(code: str) -> bool:
    """Validate the check digit of an 18-digit SSCC.

    This filters out most OCR misreadings, since a single incorrectly
    recognized digit will usually invalidate the check digit.
    """
    if not is_valid_code(code):
        return False
    return int(code[17]) == sscc_check_digit(code)
