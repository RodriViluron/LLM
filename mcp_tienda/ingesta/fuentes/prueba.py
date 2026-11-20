"""Fuente del catálogo de prueba (escenario B): lee el JSON que arma generar_catalogo_prueba."""

import json
from collections.abc import Iterator
from pathlib import Path

from mcp_tienda.config import DIR_CATALOGO_PRUEBA
from mcp_tienda.modelos import ProductoCrudo


class FuentePrueba:
    nombre = "prueba"

    def __init__(self, ruta: Path | None = None):
        self.ruta = ruta or DIR_CATALOGO_PRUEBA / "productos_crudos.json"

    def iterar_productos(self) -> Iterator[ProductoCrudo]:
        for item in json.loads(self.ruta.read_text(encoding="utf-8")):
            yield ProductoCrudo.model_validate(item)
