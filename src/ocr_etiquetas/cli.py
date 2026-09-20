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
    parser.add_argument("carpeta", type=Path, help="Carpeta con las imágenes de etiquetas")
    parser.add_argument(
        "-s", "--salida", type=Path, required=True, help="Fichero CSV de resultados"
    )
    parser.add_argument("--prefijo", default="4260", help="Prefijo conocido del código")
    parser.add_argument("--longitud", type=int, default=18, help="Longitud total del código")
    parser.add_argument(
        "--validar-sscc",
        action="store_true",
        help="Descartar códigos cuyo dígito de control GS1 (módulo 10) no cuadre",
    )
    parser.add_argument("--cpu", action="store_true", help="Forzar ejecución sin GPU")
    parser.add_argument("-v", "--verboso", action="store_true", help="Traza detallada")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-etiquetas",
        description="Extracción por OCR de códigos numéricos en fotografías de etiquetas.",
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    extraer = subcomandos.add_parser(
        "extraer", help="Procesa una carpeta completa (reanudable)"
    )
    _argumentos_comunes(extraer)
    extraer.add_argument(
        "--angulos",
        type=int,
        nargs="+",
        default=list(ANGULOS_POR_DEFECTO),
        help="Rotaciones a probar, en grados",
    )
    extraer.add_argument("--escala", type=int, default=2, help="Factor de ampliación")
    extraer.add_argument("--contraste", type=float, default=1.5, help="Refuerzo de contraste")
    extraer.add_argument(
        "--reintentar-fallidos",
        action="store_true",
        help="Al reanudar, volver a intentar los archivos sin resultado",
    )

    rescate = subcomandos.add_parser(
        "rescate", help="Pasada agresiva sobre imágenes concretas"
    )
    _argumentos_comunes(rescate)
    rescate.add_argument(
        "-i",
        "--imagenes",
        nargs="+",
        default=None,
        help="Nombres de archivo a rescatar (por defecto, toda la carpeta)",
    )
    rescate.add_argument(
        "--sin-patron-amplio",
        action="store_true",
        help="No recurrir a la búsqueda de cualquier cadena alfanumérica",
    )

    return parser


def _comando_extraer(args: argparse.Namespace) -> int:
    patron = construir_patron(args.prefijo, args.longitud)
    imagenes = listar_imagenes(args.carpeta)
    if not imagenes:
        logger.error("No se han encontrado imágenes en %s", args.carpeta)
        return 1

    with AlmacenResultados(args.salida, args.reintentar_fallidos) as almacen:
        pendientes = [img for img in imagenes if not almacen.ya_procesado(img.name)]
        omitidas = len(imagenes) - len(pendientes)
        if omitidas:
            logger.info("Reanudando: se omiten %d archivos ya procesados", omitidas)

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
                logger.exception("Error procesando %s", imagen.name)
                continue

            almacen.guardar(imagen.name, codigos)
            total += len(codigos)
            estado = ", ".join(codigos) if codigos else "sin coincidencias"
            logger.info("[%d/%d] %s -> %s", indice, len(pendientes), imagen.name, estado)

    logger.info("Finalizado. %d códigos en %s", total, args.salida)
    return 0


def _comando_rescate(args: argparse.Namespace) -> int:
    patron = construir_patron(args.prefijo, args.longitud)
    amplio = None if args.sin_patron_amplio else construir_patron_amplio(args.longitud)

    if args.imagenes:
        objetivos = [args.carpeta / nombre for nombre in args.imagenes]
    else:
        objetivos = listar_imagenes(args.carpeta)

    with AlmacenResultados(args.salida) as almacen:
        lector = crear_lector(gpu=not args.cpu)
        rescatados = 0
        for imagen in objetivos:
            if not es_imagen(imagen):
                logger.warning("No es una imagen accesible: %s", imagen)
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
                logger.exception("Error procesando %s", imagen.name)
                continue

            almacen.guardar(imagen.name, codigos, metodo="rescate", texto_ocr=texto[:120])
            if codigos:
                rescatados += 1
                logger.info("Rescatado %s -> %s", imagen.name, ", ".join(codigos))
            else:
                logger.warning("Fallo en %s. El OCR leyó: %r", imagen.name, texto[:60])

    logger.info("Rescate finalizado. %d imágenes resueltas en %s", rescatados, args.salida)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    _configurar_logging(args.verboso)

    if not args.carpeta.is_dir():
        logger.error("La carpeta %s no existe", args.carpeta)
        return 1

    if args.comando == "extraer":
        return _comando_extraer(args)
    return _comando_rescate(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
