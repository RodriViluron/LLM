from pathlib import Path

import pytest

from mcp_tienda.catalogo import Catalogo
from mcp_tienda.cliente import ClienteTienda
from mcp_tienda.ingesta.cargar import cargar
from mcp_tienda.ingesta.fuentes import FuentePrueba

# Tabla de gamas de prueba: los tests no dependen de la documentación real de rag/docs/.
TABLA_GAMAS = Path(__file__).parent / "datos" / "tabla_gamas_prueba.md"


@pytest.fixture(scope="session")
def catalogo(tmp_path_factory) -> Catalogo:
    """Catálogo de prueba cargado en una base temporal (no toca datos/catalogo.sqlite)."""
    ruta = tmp_path_factory.mktemp("datos") / "catalogo.sqlite"
    cargar(FuentePrueba(), ruta)
    return Catalogo(ruta)


@pytest.fixture(scope="session")
def cliente(catalogo) -> ClienteTienda:
    """Servidor MCP real de la tienda, levantado una vez sobre el catálogo temporal."""
    cliente = ClienteTienda(catalogo_db=catalogo.ruta_db, entorno={"AMN_TABLA_GAMAS": str(TABLA_GAMAS)})
    yield cliente
    cliente.cerrar()
