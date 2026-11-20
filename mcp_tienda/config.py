"""Rutas y configuración compartida. Todo sale de variables de entorno con valores por defecto."""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DIR_DATOS = RAIZ / "datos"
DIR_ESQUEMAS = DIR_DATOS / "esquemas"
DIR_CATALOGO_PRUEBA = DIR_DATOS / "catalogo_prueba"


def ruta_catalogo_db() -> Path:
    """Ruta de la base SQLite del catálogo (se puede cambiar con AMN_CATALOGO_DB)."""
    ruta = Path(os.getenv("AMN_CATALOGO_DB", "datos/catalogo.sqlite"))
    return ruta if ruta.is_absolute() else RAIZ / ruta
