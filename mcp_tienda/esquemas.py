"""Carga de los esquemas de atributos y normalización de categorías."""

import re
import unicodedata
from functools import cache

import yaml

from mcp_tienda.config import DIR_ESQUEMAS
from mcp_tienda.modelos import Esquema


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples. Sirve para comparar texto de distintas fuentes."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


@cache
def cargar_esquemas() -> dict[str, Esquema]:
    esquemas = {}
    for ruta in sorted(DIR_ESQUEMAS.glob("*.yaml")):
        esquema = Esquema.model_validate(yaml.safe_load(ruta.read_text(encoding="utf-8")))
        esquemas[esquema.categoria] = esquema
    return esquemas


def normalizar_categoria(categoria_origen: str) -> str:
    """Traduce la categoría de la fuente («Placas de Video», «Micros AMD») a la propia («gpu», «cpu»).

    Gana el sinónimo más largo que aparezca como palabras completas, para que
    «Refrigeración CPU» sea cooler y no cpu. Si no coincide nada, devuelve «otros».
    """
    texto = f" {normalizar_texto(categoria_origen)} "
    mejor, largo_mejor = "otros", 0
    for categoria, esquema in cargar_esquemas().items():
        for sinonimo in esquema.sinonimos:
            s = normalizar_texto(sinonimo)
            if f" {s} " in texto and len(s) > largo_mejor:
                mejor, largo_mejor = categoria, len(s)
    return mejor
