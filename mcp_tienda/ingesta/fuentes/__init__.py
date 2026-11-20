"""Fuentes de catálogo intercambiables. Todas cumplen el contrato de base.FuenteCatalogo."""

import os

from mcp_tienda.ingesta.fuentes.api import FuenteAPI
from mcp_tienda.ingesta.fuentes.base import FuenteCatalogo
from mcp_tienda.ingesta.fuentes.export_csv import FuenteCSV
from mcp_tienda.ingesta.fuentes.prueba import FuentePrueba


def _cookie_de_sesion() -> str | None:
    """Cookie de sesión de la tienda, para que la API muestre precios.

    AMN_API_COOKIE es la cookie completa (nombre=valor). Si solo se cargó el valor en AMN_API_TOKEN,
    se arma con el nombre que usa la tienda en producción.
    """
    if cookie := os.getenv("AMN_API_COOKIE"):
        return cookie
    if valor := os.getenv("AMN_API_TOKEN"):
        return f"__Secure-better-auth.session_token={valor}"
    return None


def obtener_fuente(nombre: str, archivo: str | None = None) -> FuenteCatalogo:
    if nombre == "prueba":
        return FuentePrueba()
    if nombre == "csv":
        if not archivo:
            raise ValueError("La fuente csv necesita --archivo")
        return FuenteCSV(archivo)
    if nombre == "api":
        return FuenteAPI(os.getenv("AMN_API_URL", ""), _cookie_de_sesion())
    raise ValueError(f"Fuente desconocida: {nombre}")


__all__ = ["FuenteAPI", "FuenteCSV", "FuenteCatalogo", "FuentePrueba", "obtener_fuente"]
