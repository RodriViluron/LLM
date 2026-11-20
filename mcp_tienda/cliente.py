"""Puente entre el agente (sincrónico) y el servidor MCP de la tienda.

`langchain-mcp-adapters` convierte las tools del servidor MCP en tools de LangChain, pero:
- son asíncronas, y el agente (como el del ejemplo de la cátedra) se usa de forma sincrónica;
- si no se le da una sesión abierta, levanta un servidor nuevo en cada llamada.

Este módulo resuelve las dos cosas: mantiene UN servidor abierto en un hilo aparte durante toda
la vida del programa y entrega las mismas tools en versión sincrónica. Cada tool conserva su
nombre, su descripción y sus argumentos; el texto va al modelo y los datos completos al `artifact`.

Uso:
    cliente = get_cliente()
    cliente.tools()                                   # tools de LangChain para el agente
    texto, datos = cliente.llamar("obtener_producto", codigo="CAB002")   # llamada directa desde código
"""

import asyncio
import atexit
import json
import os
import sys
import threading
from functools import cache
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from mcp_tienda.config import RAIZ

SERVIDOR = "tienda-amn"
TIEMPO_MAXIMO_S = 60


class ClienteTienda:
    def __init__(self, catalogo_db: Path | str | None = None, entorno: dict[str, str] | None = None):
        """Levanta el servidor MCP.

        `catalogo_db` lo apunta a otra base y `entorno` le agrega variables (lo usan los tests).
        """
        entorno = {**os.environ, **(entorno or {})}
        if catalogo_db is not None:
            entorno["AMN_CATALOGO_DB"] = str(catalogo_db)
        self._conexion = {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "mcp_tienda.servidor"],
            "cwd": str(RAIZ),
            "env": entorno,
        }
        self._asincronicas: dict[str, BaseTool] = {}
        self._error: BaseException | None = None
        self._listo = threading.Event()
        self._loop = asyncio.new_event_loop()
        self._cerrar: asyncio.Event | None = None
        self._hilo = threading.Thread(target=self._loop.run_forever, name="mcp-tienda", daemon=True)
        self._hilo.start()
        self._tarea = asyncio.run_coroutine_threadsafe(self._mantener_sesion(), self._loop)
        if not self._listo.wait(TIEMPO_MAXIMO_S) or self._error:
            raise RuntimeError(f"No se pudo iniciar el servidor MCP de la tienda: {self._error or 'no respondió'}")

    async def _mantener_sesion(self) -> None:
        """Abre la sesión y la deja abierta hasta que se pida cerrar (todo dentro de la misma tarea)."""
        self._cerrar = asyncio.Event()
        try:
            cliente = MultiServerMCPClient({SERVIDOR: self._conexion})
            async with cliente.session(SERVIDOR) as sesion:
                herramientas = await load_mcp_tools(sesion)
                self._asincronicas = {t.name: t for t in herramientas}
                self._listo.set()
                await self._cerrar.wait()
        except BaseException as e:   # se informa al hilo que está esperando
            self._error = e
            self._listo.set()

    def llamar(self, nombre: str, **argumentos) -> tuple[str, dict | None]:
        """Ejecuta una tool del servidor. Devuelve (texto para el modelo, datos completos)."""
        if nombre not in self._asincronicas:
            raise KeyError(f"El servidor MCP no tiene la tool '{nombre}'. Tiene: {', '.join(self._asincronicas)}")
        argumentos = {k: v for k, v in argumentos.items() if v is not None}
        futuro = asyncio.run_coroutine_threadsafe(self._asincronicas[nombre].coroutine(**argumentos), self._loop)
        contenido, artifact = futuro.result(TIEMPO_MAXIMO_S)
        texto = "".join(b["text"] for b in contenido if b.get("type") == "text") if isinstance(contenido, list) \
            else str(contenido)
        return texto, (artifact or {}).get("structured_content")

    def llamar_json(self, nombre: str, **argumentos) -> tuple[dict, dict | None]:
        """Como `llamar`, pero con el texto ya interpretado como JSON."""
        texto, datos = self.llamar(nombre, **argumentos)
        return json.loads(texto), datos

    def tools(self) -> list[BaseTool]:
        """Las tools del servidor como tools sincrónicas de LangChain, listas para create_agent."""
        return [self._sincronica(t) for t in self._asincronicas.values()]

    def _sincronica(self, tool: BaseTool) -> BaseTool:
        def ejecutar(**argumentos):
            return self.llamar(tool.name, **argumentos)

        return StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            func=ejecutar,
            response_format="content_and_artifact",   # (texto para el modelo, datos para la interfaz)
            # Si el modelo manda un argumento inválido (por ejemplo categoria="placa de video"), el
            # servidor lo rechaza y el adaptador lanza una excepción que cortaría el turno. Así, el
            # error le vuelve al modelo como texto y puede corregir la llamada.
            handle_tool_error=True,
        )

    def cerrar(self) -> None:
        if self._loop.is_closed():
            return
        if self._cerrar is not None:
            self._loop.call_soon_threadsafe(self._cerrar.set)
            try:
                self._tarea.result(10)
            except Exception:   # noqa: BLE001  (al cerrar, lo que importa es no colgar el programa)
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._hilo.join(5)
        if not self._loop.is_running():
            self._loop.close()


@cache
def get_cliente() -> ClienteTienda:
    """El cliente de la aplicación: un solo servidor MCP para todo el programa."""
    cliente = ClienteTienda()
    atexit.register(cliente.cerrar)
    return cliente
