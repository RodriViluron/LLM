"""Fuente desde la API de la tienda (escenario A): `GET /api/products`, de a 100 productos.

Qué entrega la API (ver DEVELOPER_API_MANUAL de la tienda):
- el listado es público y pagina con `page` y `limit` (máximo 100); `pagination.hasNextPage` avisa si sigue;
- cada elemento trae `product` (sku, name, desc, hdesc, category, brand, imageUrl) e `inventory.totalQty`;
- el precio (`pinpesos`, en pesos) viene vacío si no hay sesión iniciada. La sesión es una cookie.

Por eso hay dos formas de usarla:
- `iterar_items()` devuelve lo que manda la API, sin tocar. No necesita sesión. Lo usa el reporte de
  calidad del catálogo, que mira los textos y no los precios.
- `iterar_productos()` devuelve ProductoCrudoAMN, que exige precio. Necesita la sesión de una cuenta de
  la tienda (se copia del navegador después de iniciar sesión; va en el .env, nunca al repo).

Configuración (.env):
    AMN_API_URL=https://api.amn.com.ar/api
    AMN_API_TOKEN=<valor de la cookie __Secure-better-auth.session_token>
    AMN_API_COOKIE=<nombre>=<valor>        (alternativa: la cookie completa; tiene prioridad)
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator

from mcp_tienda.modelos import ProductoCrudoAMN

TAMANO_PAGINA = 100   # máximo que acepta la API
REINTENTOS = 3


class ErrorFuenteAPI(RuntimeError):
    """La API no respondió o respondió algo que no sirve para cargar el catálogo."""


class FuenteAPI:
    nombre = "api"

    def __init__(self, url: str, cookie: str | None = None, pausa: float = 0.3,
                 pedir: Callable[[str, dict], dict] | None = None):
        """`pausa` son los segundos entre pedidos (para no cargar el sitio en producción).
        `pedir(ruta, parametros)` reemplaza la conexión real; lo usan los tests."""
        if not url:
            raise ValueError("Falta AMN_API_URL")
        self.url = url.rstrip("/")
        self.cookie = cookie or None
        self.pausa = pausa
        self._pedir = pedir or self._pedir_http
        self.sin_precio = 0   # productos que la API devolvió sin precio en la última pasada

    # --- Conexión -----------------------------------------------------------------------------

    def _pedir_http(self, ruta: str, parametros: dict) -> dict:
        direccion = f"{self.url}{ruta}?{urllib.parse.urlencode(parametros)}"
        cabeceras = {"Accept": "application/json", "User-Agent": "catalog-reader/0.1"}
        if self.cookie:
            cabeceras["Cookie"] = self.cookie
        for intento in range(1, REINTENTOS + 1):
            try:
                with urllib.request.urlopen(urllib.request.Request(direccion, headers=cabeceras), timeout=30) as r:
                    datos = json.loads(r.read().decode("utf-8"))
                time.sleep(self.pausa)
                return datos
            except urllib.error.HTTPError as error:
                # 429 = demasiados pedidos; 5xx = caída momentánea. Se espera y se reintenta.
                if error.code not in (429, 502, 503, 504) or intento == REINTENTOS:
                    raise ErrorFuenteAPI(f"La API respondió {error.code} en {ruta}") from error
                espera = error.headers.get("Retry-After", "")
                time.sleep(min(int(espera), 30) if espera.isdigit() else 2 * intento)
            except (urllib.error.URLError, TimeoutError) as error:
                if intento == REINTENTOS:
                    raise ErrorFuenteAPI(f"No se pudo conectar con {self.url}: {error}") from error
                time.sleep(2 * intento)
        raise ErrorFuenteAPI(f"No se pudo leer {ruta}")

    # --- Lectura ------------------------------------------------------------------------------

    def _paginas(self) -> Iterator[dict]:
        pagina = 1
        while True:
            respuesta = self._pedir("/products", {"limit": TAMANO_PAGINA, "page": pagina,
                                                  "sortBy": "name", "sortOrder": "asc"})
            yield respuesta
            if not respuesta.get("pagination", {}).get("hasNextPage"):
                return
            pagina += 1

    def iterar_items(self) -> Iterator[dict]:
        """Los productos tal como los manda la API (sin repetir SKU). No necesita sesión."""
        vistos: set[str] = set()
        for respuesta in self._paginas():
            for item in respuesta.get("data", []):
                sku = item.get("product", {}).get("sku")
                if sku and sku not in vistos:
                    vistos.add(sku)
                    yield item

    def iterar_productos(self) -> Iterator[ProductoCrudoAMN]:
        self.sin_precio = 0
        vistos: set[str] = set()
        for respuesta in self._paginas():
            if respuesta.get("pricesVisible") is False:
                raise ErrorFuenteAPI(
                    "La API no muestra precios: falta la sesión o venció. Iniciá sesión en la tienda, copiá el valor "
                    "de la cookie «__Secure-better-auth.session_token» y pegalo en AMN_API_TOKEN (archivo .env).")
            for item in respuesta.get("data", []):
                crudo = self._mapear(item)
                if crudo is None:
                    self.sin_precio += 1
                elif crudo.codigo not in vistos:
                    vistos.add(crudo.codigo)
                    yield crudo

    @staticmethod
    def _mapear(item: dict) -> ProductoCrudoAMN | None:
        """Traduce un producto de la API a ProductoCrudoAMN. Devuelve None si no tiene precio comercial."""
        producto = item["product"]
        precio = item.get("pinpesos")
        if precio is None:
            precio = (item.get("pricing") or {}).get("pinpesos")
        if not isinstance(precio, int | float) or precio <= 0:
            return None
        categoria = producto.get("category") or {}
        stock = (item.get("inventory") or {}).get("totalQty") or 0
        return ProductoCrudoAMN(
            codigo=producto["sku"],
            nombre=producto["name"],
            descripcion=producto.get("desc") or "",
            descripcion_interna=producto.get("hdesc") or "",
            categoria=(categoria.get("name") or "").strip() or "sin categoría",
            categoria_codigo=categoria.get("code"),
            marca=(producto.get("brand") or {}).get("name"),
            precio=float(precio),
            stock=max(0, int(stock)),   # la API puede informar stock negativo; para comprar es 0
            imagen=producto.get("imageUrl"),
        )
