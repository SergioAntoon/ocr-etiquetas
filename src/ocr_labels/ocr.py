"""Read label codes using EasyOCR.

Contains two strategies:

* :func:`extract_codes` — standard pass: rotates the image, upscales it,
  and enhances contrast until matches are found.
* :func:`extract_codes_rescue` — aggressive pass for images that the
  standard strategy cannot resolve.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

from .cleaning import clean_code, is_valid_code, is_valid_sscc

logger = logging.getLogger(__name__)

try:  # Optional support for .heic iPhone photos.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    logger.warning("pillow-heif is not available: HEIC/HEIF images cannot be opened")

#: Characters that OCR may return where a digit is expected.
DIGIT_CLASS = r"[0-9OoQDIlLiZzSsGBAa\|!T]"

DEFAULT_ANGLES: tuple[int, ...] = (0, 90, 180, 270)
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif",
}


def build_pattern(prefix: str = "4260", length: int = 18) -> re.Pattern[str]:
    """Build an OCR-tolerant regular expression."""
    remaining = length - len(prefix)
    return re.compile(rf"{prefix}{DIGIT_CLASS}{{{remaining}}}", re.IGNORECASE)


#: Last resort: any alphanumeric string with the expected length.
def build_broad_pattern(length: int = 18) -> re.Pattern[str]:
    return re.compile(rf"[A-Za-z0-9]{{{length}}}")


def create_reader(languages: Sequence[str] = ("en",), gpu: bool = True):
    """Create an EasyOCR reader (models are downloaded on first use)."""
    import easyocr  # Deferred import: loading torch is slow.

    logger.info("Loading EasyOCR model (gpu=%s)...", gpu)
    return easyocr.Reader(list(languages), gpu=gpu)


def is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def list_images(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir() if is_image(path))


def _normalize_text(fragments: Iterable[str]) -> str:
    """Join OCR fragments and remove irrelevant separators."""
    text = "".join(fragments)
    for character in (" ", "-", "_", ".", ","):
        text = text.replace(character, "")
    return text


def _prepare_image(image: Image.Image, angle: int, scale: int, contrast: float) -> np.ndarray:
    rotated = image.rotate(angle, expand=True)
    width, height = rotated.size
    enlarged = rotated.resize((width * scale, height * scale), Image.Resampling.LANCZOS)
    return np.array(ImageEnhance.Contrast(enlarged).enhance(contrast))


def _clean_matches(
    raw_matches: Iterable[str],
    preserved_prefix_length: int,
    validate_sscc: bool,
) -> list[str]:
    """Clean matches and discard invalid codes."""
    cleaned = (clean_code(match, preserved_prefix_length) for match in raw_matches)
    valid = [code for code in cleaned if is_valid_code(code)]
    if validate_sscc:
        valid = [code for code in valid if is_valid_sscc(code)]
    return sorted(set(valid))


def extract_codes(
    image_path: Path,
    reader,
    pattern: re.Pattern[str],
    *,
    angles: Sequence[int] = DEFAULT_ANGLES,
    scale: int = 2,
    contrast: float = 1.5,
    validate_sscc: bool = False,
) -> list[str]:
    """Return the codes found in an image (empty list if none are found).

    Each rotation is tested, stopping at the first one that produces valid
    results to avoid unnecessary work on most photographs.
    """
    with Image.open(image_path) as file:
        image = file.convert("RGB")

    preserved_prefix_length = len(pattern.pattern.split("[")[0])
    for angle in angles:
        matrix = _prepare_image(image, angle, scale, contrast)
        text = _normalize_text(reader.readtext(matrix, detail=0))
        codes = _clean_matches(pattern.findall(text), preserved_prefix_length, validate_sscc)
        if codes:
            logger.debug(
                "%s: codes found at rotation %s°",
                image_path.name,
                angle,
            )
            return codes
    return []


def extract_codes_rescue(
    image_path: Path,
    reader,
    pattern: re.Pattern[str],
    *,
    broad_pattern: re.Pattern[str] | None = None,
    mag_ratio: float = 3.0,
    contrast_ths: float = 0.5,
    adjust_contrast: float = 0.7,
    validate_sscc: bool = False,
) -> tuple[list[str], str]:
    """Run an aggressive pass for difficult images.

    Converts the image to grayscale and forces EasyOCR's internal parameters.
    Returns both the codes and the raw OCR text, which is useful for manual
    review.
    """
    with Image.open(image_path) as file:
        matrix = np.array(file.convert("L"))

    text = _normalize_text(
        reader.readtext(
            matrix,
            detail=0,
            mag_ratio=mag_ratio,
            contrast_ths=contrast_ths,
            adjust_contrast=adjust_contrast,
        )
    )

    preserved_prefix_length = len(pattern.pattern.split("[")[0])
    codes = _clean_matches(pattern.findall(text), preserved_prefix_length, validate_sscc)
    if codes:
        return codes, text

    if broad_pattern is not None:
        # Without a reliable prefix, clean the entire code.
        codes = _clean_matches(broad_pattern.findall(text), 0, validate_sscc)
    return codes, text
