"""Persistencia de resultados en CSV con soporte de reanudación.

Los lotes grandes de fotografías tardan horas en procesarse. El almacén
escribe cada código en cuanto se lee y recuerda qué archivos ya se han
tratado, de modo que una ejecución interrumpida puede retomarse sin perder
trabajo ni duplicar filas.
"""

from __future__ import annotations
from typing import Self  # o from typing_extensions import Self
import csv
from pathlib import Path
from types import TracebackType

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
