"""Fuente desde un export CSV del panel de la tienda.

Sirve si la tienda nos pasa un Excel/CSV antes que la API. Como no sabemos cómo se llaman sus
columnas, se pasa un mapeo «campo nuestro → columna de ellos».
"""

import csv
import re
from collections.abc import Iterator
from pathlib import Path

from mcp_tienda.modelos import ProductoCrudo

COLUMNAS_POR_DEFECTO = {
    "codigo": "codigo", "nombre": "nombre", "descripcion": "descripcion", "categoria": "categoria",
    "marca": "marca", "precio": "precio", "stock": "stock", "url": "url", "imagen": "imagen",
}


def parsear_precio(texto: str) -> float:
    """Entiende precios en formato argentino: «$ 145.000,50», «145000», «145.000», «145,5»."""
    t = re.sub(r"[^\d.,]", "", texto)
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    return float(t)


class FuenteCSV:
    nombre = "csv"

    def __init__(self, ruta: Path, columnas: dict[str, str] | None = None, separador: str = ","):
        self.ruta = Path(ruta)
        self.columnas = {**COLUMNAS_POR_DEFECTO, **(columnas or {})}
        self.separador = separador

    def iterar_productos(self) -> Iterator[ProductoCrudo]:
        with self.ruta.open(encoding="utf-8-sig", newline="") as archivo:
            for fila in csv.DictReader(archivo, delimiter=self.separador):
                def campo(nombre: str, fila: dict = fila) -> str | None:
                    valor = fila.get(self.columnas[nombre])
                    return valor.strip() if valor and valor.strip() else None

                yield ProductoCrudo(
                    codigo=campo("codigo"), nombre=campo("nombre"),
                    descripcion=campo("descripcion") or "", categoria=campo("categoria") or "",
                    marca=campo("marca"), precio=parsear_precio(campo("precio") or "0"),
                    stock=int(float(campo("stock") or 0)), url=campo("url"), imagen=campo("imagen"),
                )
