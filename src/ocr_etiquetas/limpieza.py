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


def limpiar_codigo(texto: str, caracteres_intactos: int = 4) -> str:
    """Replace letters with the digits they are commonly confused with.

    The first ``caracteres_intactos`` characters are left unchanged because
    the code prefix is known and has already been validated by the regular
    expression.

    >>> limpiar_codigo("4260OI2345678901Z5")
    '426001234567890125'
    """
    prefijo = texto[:caracteres_intactos]
    resto = texto[caracteres_intactos:]
    for letra, numero in REEMPLAZOS.items():
        resto = resto.replace(letra, numero)
    return prefijo + resto


def es_codigo_valido(codigo: str) -> bool:
    """Check that the code is numeric and has the expected length."""
    return codigo.isdigit() and len(codigo) == LONGITUD_CODIGO


def digito_control_sscc(codigo: str) -> int:
    """Calculate the GS1 check digit (modulo 10) of an SSCC.

    Accepts either the complete code or its first 17 digits.
    """
    base = codigo[:17]
    if len(base) != 17 or not base.isdigit():
        raise ValueError("17 digits are required to calculate the check digit")
    suma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(base))
    return (10 - suma % 10) % 10


def es_sscc_valido(codigo: str) -> bool:
    """Validate the check digit of an 18-digit SSCC.

    This filters out most OCR misreadings, since a single incorrectly
    recognized digit will usually invalidate the check digit.
    """
    if not es_codigo_valido(codigo):
        return False
    return int(codigo[17]) == digito_control_sscc(codigo)
