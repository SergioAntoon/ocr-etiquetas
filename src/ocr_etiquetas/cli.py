"""Command-line interface for OCR-based label code extraction."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .almacen import AlmacenResultados
from .ocr import (
    ANGULOS_POR_DEFECTO,
    construir_patron,
    construir_patron_amplio,
    crear_lector,
    es_imagen,
    extraer_codigos,
    extraer_codigos_rescate,
    listar_imagenes,
)

logger = logging.getLogger("ocr_etiquetas")


def _configurar_logging(verboso: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _argumentos_comunes(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "carpeta",
        type=Path,
        help="Folder containing label images",
    )
    parser.add_argument(
        "-s",
        "--salida",
        type=Path,
        required=True,
        help="Output CSV results file",
    )
    parser.add_argument(
        "--prefijo",
        default="4260",
        help="Known code prefix",
    )
    parser.add_argument(
        "--longitud",
        type=int,
        default=18,
        help="Total code length",
    )
    parser.add_argument(
        "--validar-sscc",
        action="store_true",
        help="Discard codes with an invalid GS1 check digit (modulo 10)",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU-only execution",
    )
    parser.add_argument(
        "-v",
        "--verboso",
        action="store_true",
        help="Enable detailed logging",
    )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-etiquetas",
        description="OCR-based extraction of numeric codes from label images.",
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    extraer = subcomandos.add_parser(
        "extraer",
        help="Process an entire folder of images with resume support",
    )
    _argumentos_comunes(extraer)
    extraer.add_argument(
        "--angulos",
        type=int,
        nargs="+",
        default=list(ANGULOS_POR_DEFECTO),
        help="Rotation angles to try, in degrees",
    )
    extraer.add_argument(
        "--escala",
        type=int,
        default=2,
        help="Image scaling factor",
    )
    extraer.add_argument(
        "--contraste",
        type=float,
        default=1.5,
        help="Contrast enhancement",
    )
    extraer.add_argument(
        "--reintentar-fallidos",
        action="store_true",
        help="Retry files without results when resuming",
    )

    rescate = subcomandos.add_parser(
        "rescate",
        help="Aggressive OCR pass over selected images",
    )
    _argumentos_comunes(rescate)
    rescate.add_argument(
        "-i",
        "--imagenes",
        nargs="+",
        default=None,
        help="File names to process in rescue mode (defaults to the entire folder)",
    )
    rescate.add_argument(
        "--sin-patron-amplio",
        action="store_true",
        help="Do not fall back to searching for any alphanumeric string",
    )

    return parser


def _comando_extraer(args: argparse.Namespace) -> int:
    patron = construir_patron(args.prefijo, args.longitud)
    imagenes = listar_imagenes(args.carpeta)

    if not imagenes:
        logger.error("No images found in %s", args.carpeta)
        return 1

    with AlmacenResultados(args.salida, args.reintentar_fallidos) as almacen:
        pendientes = [img for img in imagenes if not almacen.ya_procesado(img.name)]
        omitidas = len(imagenes) - len(pendientes)

        if omitidas:
            logger.info(
                "Resuming: skipping %d already processed files",
                omitidas,
            )

        lector = crear_lector(gpu=not args.cpu)
        total = 0

        for indice, imagen in enumerate(pendientes, start=1):
            try:
                codigos = extraer_codigos(
                    imagen,
                    lector,
                    patron,
                    angulos=args.angulos,
                    escala=args.escala,
                    contraste=args.contraste,
                    validar_sscc=args.validar_sscc,
                )
            except Exception:
                logger.exception("Error processing %s", imagen.name)
                continue

            almacen.guardar(imagen.name, codigos)
            total += len(codigos)
            estado = ", ".join(codigos) if codigos else "no matches"

            logger.info(
                "[%d/%d] %s -> %s",
                indice,
                len(pendientes),
                imagen.name,
                estado,
            )

    logger.info(
        "Finished. %d codes saved to %s",
        total,
        args.salida,
    )
    return 0


def _comando_rescate(args: argparse.Namespace) -> int:
    patron = construir_patron(args.prefijo, args.longitud)
    amplio = (
        None
        if args.sin_patron_amplio
        else construir_patron_amplio(args.longitud)
    )

    if args.imagenes:
        objetivos = [args.carpeta / nombre for nombre in args.imagenes]
    else:
        objetivos = listar_imagenes(args.carpeta)

    with AlmacenResultados(args.salida) as almacen:
        lector = crear_lector(gpu=not args.cpu)
        rescatados = 0

        for imagen in objetivos:
            if not es_imagen(imagen):
                logger.warning("Not an accessible image: %s", imagen)
                continue

            try:
                codigos, texto = extraer_codigos_rescate(
                    imagen,
                    lector,
                    patron,
                    patron_amplio=amplio,
                    validar_sscc=args.validar_sscc,
                )
            except Exception:
                logger.exception("Error processing %s", imagen.name)
                continue

            almacen.guardar(
                imagen.name,
                codigos,
                metodo="rescate",
                texto_ocr=texto[:120],
            )

            if codigos:
                rescatados += 1
                logger.info(
                    "Recovered %s -> %s",
                    imagen.name,
                    ", ".join(codigos),
                )
            else:
                logger.warning(
                    "Failed on %s. OCR read: %r",
                    imagen.name,
                    texto[:60],
                )

    logger.info(
        "Rescue completed. %d images recovered in %s",
        rescatados,
        args.salida,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    _configurar_logging(args.verboso)

    if not args.carpeta.is_dir():
        logger.error("Folder does not exist: %s", args.carpeta)
        return 1

    if args.comando == "extraer":
        return _comando_extraer(args)

    return _comando_rescate(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())