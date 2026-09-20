"""Command-line interface for OCR-based label code extraction."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .ocr import (
    DEFAULT_ANGLES,
    build_broad_pattern,
    build_pattern,
    create_reader,
    extract_codes,
    extract_codes_rescue,
    is_image,
    list_images,
)
from .storage import ResultStore

logger = logging.getLogger("ocr_labels")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing label images",
    )
    parser.add_argument(
        "-s",
        "--output",
        type=Path,
        required=True,
        help="Output CSV results file",
    )
    parser.add_argument(
        "--prefix",
        default="4260",
        help="Known code prefix",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=18,
        help="Total code length",
    )
    parser.add_argument(
        "--validate-sscc",
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
        "--verbose",
        action="store_true",
        help="Enable detailed logging",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-labels",
        description="OCR-based extraction of numeric codes from label images.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    extract_parser = subcommands.add_parser(
        "extract",
        help="Process an entire folder of images with resume support",
    )
    _add_common_arguments(extract_parser)
    extract_parser.add_argument(
        "--angles",
        type=int,
        nargs="+",
        default=list(DEFAULT_ANGLES),
        help="Rotation angles to try, in degrees",
    )
    extract_parser.add_argument(
        "--scale",
        type=int,
        default=2,
        help="Image scaling factor",
    )
    extract_parser.add_argument(
        "--contrast",
        type=float,
        default=1.5,
        help="Contrast enhancement",
    )
    extract_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry files without results when resuming",
    )

    rescue_parser = subcommands.add_parser(
        "rescue",
        help="Aggressive OCR pass over selected images",
    )
    _add_common_arguments(rescue_parser)
    rescue_parser.add_argument(
        "-i",
        "--images",
        nargs="+",
        default=None,
        help="File names to process in rescue mode (defaults to the entire folder)",
    )
    rescue_parser.add_argument(
        "--no-broad-pattern",
        action="store_true",
        help="Do not fall back to searching for any alphanumeric string",
    )

    return parser


def _extract_command(args: argparse.Namespace) -> int:
    pattern = build_pattern(args.prefix, args.length)
    images = list_images(args.folder)

    if not images:
        logger.error("No images found in %s", args.folder)
        return 1

    with ResultStore(args.output, args.retry_failed) as store:
        pending = [image for image in images if not store.is_processed(image.name)]
        skipped = len(images) - len(pending)

        if skipped:
            logger.info(
                "Resuming: skipping %d already processed files",
                skipped,
            )

        reader = create_reader(gpu=not args.cpu)
        total = 0

        for index, image in enumerate(pending, start=1):
            try:
                codes = extract_codes(
                    image,
                    reader,
                    pattern,
                    angles=args.angles,
                    scale=args.scale,
                    contrast=args.contrast,
                    validate_sscc=args.validate_sscc,
                )
            except Exception:
                logger.exception("Error processing %s", image.name)
                continue

            store.save(image.name, codes)
            total += len(codes)
            status = ", ".join(codes) if codes else "no matches"

            logger.info(
                "[%d/%d] %s -> %s",
                index,
                len(pending),
                image.name,
                status,
            )

    logger.info(
        "Finished. %d codes saved to %s",
        total,
        args.output,
    )
    return 0


def _rescue_command(args: argparse.Namespace) -> int:
    pattern = build_pattern(args.prefix, args.length)
    broad_pattern = (
        None
        if args.no_broad_pattern
        else build_broad_pattern(args.length)
    )

    if args.images:
        targets = [args.folder / name for name in args.images]
    else:
        targets = list_images(args.folder)

    with ResultStore(args.output) as store:
        reader = create_reader(gpu=not args.cpu)
        recovered = 0

        for image in targets:
            if not is_image(image):
                logger.warning("Not an accessible image: %s", image)
                continue

            try:
                codes, ocr_text = extract_codes_rescue(
                    image,
                    reader,
                    pattern,
                    broad_pattern=broad_pattern,
                    validate_sscc=args.validate_sscc,
                )
            except Exception:
                logger.exception("Error processing %s", image.name)
                continue

            store.save(
                image.name,
                codes,
                method="rescue",
                ocr_text=ocr_text[:120],
            )

            if codes:
                recovered += 1
                logger.info(
                    "Recovered %s -> %s",
                    image.name,
                    ", ".join(codes),
                )
            else:
                logger.warning(
                    "Failed on %s. OCR read: %r",
                    image.name,
                    ocr_text[:60],
                )

    logger.info(
        "Rescue completed. %d images recovered in %s",
        recovered,
        args.output,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose)

    if not args.folder.is_dir():
        logger.error("Folder does not exist: %s", args.folder)
        return 1

    if args.command == "extract":
        return _extract_command(args)

    return _rescue_command(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
