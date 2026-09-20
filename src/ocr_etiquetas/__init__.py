"""OCR-based extraction of numeric codes from label images."""

__version__ = "1.0.0"
__author__ = "Sergio Antón"

from .limpieza import es_sscc_valido, limpiar_codigo
from .ocr import extraer_codigos, extraer_codigos_rescate

__all__ = [
    "__version__",
    "es_sscc_valido",
    "extraer_codigos",
    "extraer_codigos_rescate",
    "limpiar_codigo",
]
