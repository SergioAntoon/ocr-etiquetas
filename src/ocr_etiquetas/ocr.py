"""Read label codes using EasyOCR.

Contains two strategies:

* :func:`extraer_codigos` — standard pass: rotates the image, upscales it,
  and enhances contrast until matches are found.
* :func:`extraer_codigos_rescate` — aggressive pass for images that the
  standard strategy cannot resolve.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

from .limpieza import es_codigo_valido, es_sscc_valido, limpiar_codigo

logger = logging.getLogger(__name__)

try:  # Optional support for .heic iPhone photos.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    logger.warning("pillow-heif is not available: HEIC/HEIF images cannot be opened")

#: Characters that OCR may return where a digit is expected.
_CLASE_DIGITOS = r"[0-9OoQDIlLiZzSsGBAa\|!T]"

ANGULOS_POR_DEFECTO: tuple[int, ...] = (0, 90, 180, 270)
EXTENSIONES_IMAGEN = {
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif",
}


def construir_patron(prefijo: str = "4260", longitud: int = 18) -> re.Pattern[str]:
    """Build an OCR-tolerant regular expression."""
    restantes = longitud - len(prefijo)
    return re.compile(rf"{prefijo}{_CLASE_DIGITOS}{{{restantes}}}", re.IGNORECASE)


#: Last resort: any alphanumeric string with the expected length.
def construir_patron_amplio(longitud: int = 18) -> re.Pattern[str]:
    return re.compile(rf"[A-Za-z0-9]{{{longitud}}}")


def crear_lector(idiomas: Sequence[str] = ("en",), gpu: bool = True):
    """Create an EasyOCR reader (models are downloaded on first use)."""
    import easyocr  # Deferred import: loading torch is slow.

    logger.info("Loading EasyOCR model (gpu=%s)...", gpu)
    return easyocr.Reader(list(idiomas), gpu=gpu)


def es_imagen(ruta: Path) -> bool:
    return ruta.is_file() and ruta.suffix.lower() in EXTENSIONES_IMAGEN


def listar_imagenes(carpeta: Path) -> list[Path]:
    return sorted(p for p in carpeta.iterdir() if es_imagen(p))


def _normalizar_texto(fragmentos: Iterable[str]) -> str:
    """Join OCR fragments and remove irrelevant separators."""
    texto = "".join(fragmentos)
    for caracter in (" ", "-", "_", ".", ","):
        texto = texto.replace(caracter, "")
    return texto


def _preparar(imagen: Image.Image, angulo: int, escala: int, contraste: float) -> np.ndarray:
    rotada = imagen.rotate(angulo, expand=True)
    ancho, alto = rotada.size
    ampliada = rotada.resize((ancho * escala, alto * escala), Image.Resampling.LANCZOS)
    return np.array(ImageEnhance.Contrast(ampliada).enhance(contraste))


def _depurar(
    crudos: Iterable[str],
    prefijo_intacto: int,
    validar_sscc: bool,
) -> list[str]:
    """Clean matches and discard invalid codes."""
    limpios = (limpiar_codigo(c, prefijo_intacto) for c in crudos)
    validos = [c for c in limpios if es_codigo_valido(c)]
    if validar_sscc:
        validos = [c for c in validos if es_sscc_valido(c)]
    return sorted(set(validos))


def extraer_codigos(
    ruta_imagen: Path,
    lector,
    patron: re.Pattern[str],
    *,
    angulos: Sequence[int] = ANGULOS_POR_DEFECTO,
    escala: int = 2,
    contraste: float = 1.5,
    validar_sscc: bool = False,
) -> list[str]:
    """Return the codes found in an image (empty list if none are found).

    Each rotation is tested, stopping at the first one that produces valid
    results to avoid unnecessary work on most photographs.
    """
    with Image.open(ruta_imagen) as archivo:
        imagen = archivo.convert("RGB")

    prefijo_intacto = len(patron.pattern.split("[")[0])
    for angulo in angulos:
        matriz = _preparar(imagen, angulo, escala, contraste)
        texto = _normalizar_texto(lector.readtext(matriz, detail=0))
        codigos = _depurar(patron.findall(texto), prefijo_intacto, validar_sscc)
        if codigos:
            logger.debug(
                "%s: codes found at rotation %s°",
                ruta_imagen.name,
                angulo,
            )
            return codigos
    return []


def extraer_codigos_rescate(
    ruta_imagen: Path,
    lector,
    patron: re.Pattern[str],
    *,
    patron_amplio: re.Pattern[str] | None = None,
    mag_ratio: float = 3.0,
    contrast_ths: float = 0.5,
    adjust_contrast: float = 0.7,
    validar_sscc: bool = False,
) -> tuple[list[str], str]:
    """Run an aggressive pass for difficult images.

    Converts the image to grayscale and forces EasyOCR's internal parameters.
    Returns both the codes and the raw OCR text, which is useful for manual
    review.
    """
    with Image.open(ruta_imagen) as archivo:
        matriz = np.array(archivo.convert("L"))

    texto = _normalizar_texto(
        lector.readtext(
            matriz,
            detail=0,
            mag_ratio=mag_ratio,
            contrast_ths=contrast_ths,
            adjust_contrast=adjust_contrast,
        )
    )

    prefijo_intacto = len(patron.pattern.split("[")[0])
    codigos = _depurar(patron.findall(texto), prefijo_intacto, validar_sscc)
    if codigos:
        return codigos, texto

    if patron_amplio is not None:
        # Without a reliable prefix, clean the entire code.
        codigos = _depurar(patron_amplio.findall(texto), 0, validar_sscc)
    return codigos, texto
