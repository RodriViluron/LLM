"""Contrato que cumple cualquier fuente de catálogo.

La ingesta no sabe de dónde vienen los productos: solo pide `iterar_productos()` y recibe
ProductoCrudo. Cambiar de catálogo de prueba a la API real es cambiar la fuente, nada más.
El test `tests/test_contrato_fuente.py` verifica que una fuente cumpla este contrato.
"""

from collections.abc import Iterator
from typing import Protocol

from mcp_tienda.modelos import ProductoCrudo


class FuenteCatalogo(Protocol):
    nombre: str

    def iterar_productos(self) -> Iterator[ProductoCrudo]: ...
