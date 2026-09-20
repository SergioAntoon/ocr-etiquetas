"""CSV result persistence with resume support.

Large batches of photographs can take hours to process. The storage layer
writes each detected code as soon as it is extracted and keeps track of
which files have already been processed, allowing interrupted executions
to resume without losing work or creating duplicate rows.
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import TracebackType
from typing import Self

HEADER = ("file", "code", "method", "ocr_text")


class ResultStore:
    """Write results to a CSV file and avoid reprocessing already saved files."""

    def __init__(self, path: Path, retry_failed: bool = False) -> None:
        self.path = Path(path)
        self.retry_failed = retry_failed
        self.processed: set[str] = set()
        self._file = None
        self._writer: csv.writer | None = None  # type: ignore[valid-type]

    def __enter__(self) -> Self:
        exists = self.path.exists()

        if exists:
            self.processed = self._read_processed()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open(
            "a" if exists else "w",
            encoding="utf-8",
            newline="",
        )
        self._writer = csv.writer(self._file)

        if not exists:
            self._writer.writerow(HEADER)
            self._file.flush()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._file is not None:
            self._file.close()

    def _read_processed(self) -> set[str]:
        with self.path.open("r", encoding="utf-8", newline="") as file:
            rows = [
                row
                for row in csv.DictReader(file)
                if row.get("file")
            ]

        if self.retry_failed:
            return {row["file"] for row in rows if row.get("code")}

        return {row["file"] for row in rows}

    def is_processed(self, file_name: str) -> bool:
        return file_name in self.processed

    def save(
        self,
        file_name: str,
        codes: list[str],
        method: str = "standard",
        ocr_text: str = "",
    ) -> None:
        """Add one row per code; if none are found, record the failed result."""
        if self._writer is None or self._file is None:
            raise RuntimeError(
                "The storage must be used as a context manager (with ...)"
            )

        rows = [
            (file_name, code, method, ocr_text)
            for code in codes
        ]

        if not rows:
            rows = [(file_name, "", "no_result", ocr_text)]

        self._writer.writerows(rows)
        self._file.flush()
        self.processed.add(file_name)
