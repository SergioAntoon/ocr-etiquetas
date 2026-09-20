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

CABECERA = ("archivo", "codigo", "metodo", "texto_ocr")


class AlmacenResultados:
    """Escribe resultados en CSV y evita reprocesar archivos ya guardados."""

    def __init__(self, ruta: Path, reintentar_fallidos: bool = False) -> None:
        self.ruta = Path(ruta)
        self.reintentar_fallidos = reintentar_fallidos
        self.procesados: set[str] = set()
        self._fichero = None
        self._escritor: csv.writer | None = None  # type: ignore[valid-type]

    def __enter__(self) -> Self:
        existe = self.ruta.exists()
        if existe:
            self.procesados = self._leer_procesados()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._fichero = self.ruta.open("a" if existe else "w", encoding="utf-8", newline="")
        self._escritor = csv.writer(self._fichero)
        if not existe:
            self._escritor.writerow(CABECERA)
            self._fichero.flush()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._fichero is not None:
            self._fichero.close()

    def _leer_procesados(self) -> set[str]:
        with self.ruta.open("r", encoding="utf-8", newline="") as fichero:
            filas = [fila for fila in csv.DictReader(fichero) if fila.get("archivo")]

        if self.reintentar_fallidos:
            return {fila["archivo"] for fila in filas if fila.get("codigo")}
        return {fila["archivo"] for fila in filas}

    def ya_procesado(self, nombre: str) -> bool:
        return nombre in self.procesados

    def guardar(
        self,
        archivo: str,
        codigos: list[str],
        metodo: str = "estandar",
        texto_ocr: str = "",
    ) -> None:
        """Añade una fila por código; si no hay ninguno, deja constancia del fallo."""
        if self._escritor is None or self._fichero is None:
            raise RuntimeError("El almacén debe usarse como contexto (with ...)")

        filas = [(archivo, codigo, metodo, texto_ocr) for codigo in codigos]
        if not filas:
            filas = [(archivo, "", "sin_resultado", texto_ocr)]

        self._escritor.writerows(filas)
        self._fichero.flush()
        self.procesados.add(archivo)
