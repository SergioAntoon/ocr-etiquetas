"""OCR-based extraction of numeric codes from label images."""

from .cleaning import clean_code, is_valid_sscc
from .ocr import extract_codes, extract_codes_rescue

__version__ = "1.0.0"
__author__ = "Sergio Antón"

__all__ = [
    "__version__",
    "clean_code",
    "extract_codes",
    "extract_codes_rescue",
    "is_valid_sscc",
]
