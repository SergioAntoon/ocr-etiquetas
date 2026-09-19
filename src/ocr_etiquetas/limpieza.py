"""Normalización y validación de los códigos leídos por el OCR.

El OCR confunde con frecuencia letras y dígitos (O/0, I/1, S/5...). Estas
funciones deshacen esas confusiones y permiten descartar lecturas erróneas
mediante el dígito de control del SSCC (GS1 módulo 10).
"""

from __future__ import annotations

# Mapa de caracteres que el OCR suele confundir con dígitos.
REEMPLAZOS: dict[str, str] = {
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "I": "1", "l": "1", "i": "1", "|": "1", "!": "1",
    "Z": "2", "z": "2",
    "S": "5", "s": "5",
    "G": "6",
    "B": "8",
    "A": "4", "a": "4",
    "T": "7",
}

LONGITUD_CODIGO = 18


def limpiar_codigo(texto: str, caracteres_intactos: int = 4) -> str:
    """Sustituye letras por los dígitos con los que se confunden.

    Los primeros ``caracteres_intactos`` se dejan sin tocar porque el prefijo
    del código es conocido y ya se ha validado con la expresión regular.

    >>> limpiar_codigo("4260OI2345678901Z5")
    '426001234567890125'
    """
    prefijo = texto[:caracteres_intactos]
    resto = texto[caracteres_intactos:]
    for letra, numero in REEMPLAZOS.items():
        resto = resto.replace(letra, numero)
    return prefijo + resto


def es_codigo_valido(codigo: str) -> bool:
    """Comprueba que el código sea numérico y tenga la longitud esperada."""
    return codigo.isdigit() and len(codigo) == LONGITUD_CODIGO


def digito_control_sscc(codigo: str) -> int:
    """Calcula el dígito de control GS1 (módulo 10) de un SSCC.

    Recibe el código completo o sus 17 primeros dígitos.
    """
    base = codigo[:17]
    if len(base) != 17 or not base.isdigit():
        raise ValueError("Se esperan 17 dígitos para calcular el control")
    suma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(base))
    return (10 - suma % 10) % 10


def es_sscc_valido(codigo: str) -> bool:
    """Valida el dígito de control de un SSCC de 18 dígitos.

    Filtra la mayoría de lecturas erróneas del OCR, ya que un único dígito
    mal leído rompe la suma de control.
    """
    if not es_codigo_valido(codigo):
        return False
    return int(codigo[17]) == digito_control_sscc(codigo)
