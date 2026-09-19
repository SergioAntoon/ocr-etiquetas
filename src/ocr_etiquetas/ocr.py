"""Lectura de códigos de etiquetas mediante EasyOCR.

Contiene dos estrategias:

* :func:`extraer_codigos` — pasada estándar: rota la imagen, la amplía y
  refuerza el contraste hasta encontrar coincidencias.
* :func:`extraer_codigos_rescate` — pasada agresiva para las imágenes que la
  estrategia estándar no consigue resolver.
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

try:  # Soporte opcional para fotografías .heic de iPhone.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    logger.warning("pillow-heif no disponible: no se podrán abrir imágenes HEIC/HEIF")

#: Caracteres que el OCR puede devolver donde debería haber un dígito.
_CLASE_DIGITOS = r"[0-9OoQDIlLiZzSsGBAa\|!T]"

ANGULOS_POR_DEFECTO: tuple[int, ...] = (0, 90, 180, 270)
EXTENSIONES_IMAGEN = {
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif",
}


def construir_patron(prefijo: str = "4260", longitud: int = 18) -> re.Pattern[str]:
    """Crea la expresión regular tolerante a errores del OCR."""
    restantes = longitud - len(prefijo)
    return re.compile(rf"{prefijo}{_CLASE_DIGITOS}{{{restantes}}}", re.IGNORECASE)


#: Último recurso: cualquier cadena alfanumérica de la longitud esperada.
def construir_patron_amplio(longitud: int = 18) -> re.Pattern[str]:
    return re.compile(rf"[A-Za-z0-9]{{{longitud}}}")


def crear_lector(idiomas: Sequence[str] = ("en",), gpu: bool = True):
    """Instancia el lector de EasyOCR (descarga los modelos la primera vez)."""
    import easyocr  # Import diferido: cargar torch es lento.

    logger.info("Cargando modelo EasyOCR (gpu=%s)...", gpu)
    return easyocr.Reader(list(idiomas), gpu=gpu)


def es_imagen(ruta: Path) -> bool:
    return ruta.is_file() and ruta.suffix.lower() in EXTENSIONES_IMAGEN


def listar_imagenes(carpeta: Path) -> list[Path]:
    return sorted(p for p in carpeta.iterdir() if es_imagen(p))


def _normalizar_texto(fragmentos: Iterable[str]) -> str:
    """Une los fragmentos del OCR y elimina separadores irrelevantes."""
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
    """Limpia las coincidencias y descarta las que no son códigos válidos."""
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
    """Devuelve los códigos encontrados en una imagen (lista vacía si ninguno).

    Prueba cada rotación y se detiene en la primera que produce resultados
    válidos, evitando trabajo innecesario en la mayoría de fotografías.
    """
    with Image.open(ruta_imagen) as archivo:
        imagen = archivo.convert("RGB")

    prefijo_intacto = len(patron.pattern.split("[")[0])
    for angulo in angulos:
        matriz = _preparar(imagen, angulo, escala, contraste)
        texto = _normalizar_texto(lector.readtext(matriz, detail=0))
        codigos = _depurar(patron.findall(texto), prefijo_intacto, validar_sscc)
        if codigos:
            logger.debug("%s: códigos hallados con rotación %s°", ruta_imagen.name, angulo)
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
    """Pasada agresiva para imágenes difíciles.

    Convierte a escala de grises y fuerza los parámetros internos de EasyOCR.
    Devuelve los códigos y el texto crudo leído, útil para revisión manual.
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
        # Sin prefijo fiable: se limpia el código entero.
        codigos = _depurar(patron_amplio.findall(texto), 0, validar_sscc)
    return codigos, texto
