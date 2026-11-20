"""Servicio HTTP del agente: lo que la tienda (NestJS / Next.js) integra.

El agente es un servicio aparte. El backend de la tienda le manda el mensaje del usuario y recibe
un flujo de *eventos públicos* (Server-Sent Events). La interfaz solo los dibuja.

    POST /chat                       un turno de conversación; responde text/event-stream
    GET  /conversaciones/{id}        historial visible y armado actual (para reabrir el chat)
    GET  /salud                      para saber si el servicio está vivo

Qué sale y qué no sale de acá (el contrato está en docs/GUIA_INTEGRACION.md):

- SALE: el texto del agente, los productos encontrados, el armado con su compatibilidad, las
  preguntas con opciones, las fuentes y un aviso corto de lo que está haciendo («Buscando...»).
- NO SALE: el razonamiento del modelo, los argumentos y el texto crudo de las tools, la lista de
  TODOs ni las descripciones internas del catálogo. El razonamiento solo se emite si el servicio
  se levanta con AGENTE_DEPURAR=1 y el pedido lo solicita (para desarrollo).

El agente nunca confirma un pedido: el evento `armado` trae la lista de códigos y cantidades, y
es la página la que la carga en el carrito o en «Armá tu PC» cuando el usuario hace clic.

Levantar:   uv run python -m uvicorn servicio:app --port 8000
Variables:  AGENTE_CLAVE               si está definida, cada pedido tiene que traerla en la cabecera X-Agente-Clave
            AGENTE_DEPURAR             1 = permite pedir el razonamiento (solo desarrollo)
            AGENTE_MODELOS_PERMITIDOS  modelos aceptados en POST /chat, separados por coma (por defecto: local)
"""

import json
import logging
import os
import threading
from collections.abc import Iterable, Iterator
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import armado
from agente import OPCION_LOCAL, get_agent, opciones_de_modelo, saved_state, saved_turns, stream_turn

registro = logging.getLogger("servicio")

# Qué se le cuenta al usuario mientras el agente trabaja. Nunca los argumentos de la tool.
ESTADOS = {
    "buscar_productos": "Buscando productos…",
    "buscar_pieza_armado": "Buscando piezas para el armado…",
    "validar_presupuesto": "Revisando el presupuesto…",
    "obtener_producto": "Consultando el producto…",
    "verificar_compatibilidad": "Verificando la compatibilidad…",
    "consultar_caracteristicas": "Consultando la documentación…",
    "buscar_especificaciones_web": "Buscando en internet…",
    "iniciar_configuracion": "Empezando el armado…",
    "agregar_o_reemplazar_componente": "Agregando una pieza al armado…",
    "ajustar_presupuesto": "Ajustando el armado al presupuesto…",
    "obtener_configuracion": "Revisando el armado…",
    "load_skill": "Preparando el procedimiento…",
}
PREGUNTAS = {"preguntar_al_usuario"}   # tool que muestra una pregunta con botones
SIN_AVISO = {"write_todos", "read_todos", "siguiente_pregunta_armado", *PREGUNTAS}   # pasos internos: no generan aviso

MOSTRAR, OPCIONAL, INTERNO = "mostrar", "opcional", "interno"


# ---------------------------------------------------------------------------
# De los datos internos a lo que puede ver el cliente
# ---------------------------------------------------------------------------

def producto_publico(p: dict) -> dict:
    """Lo que la interfaz necesita para dibujar una tarjeta. Sin descripción ni campos internos."""
    return {
        "codigo": p["codigo"], "nombre": " ".join(p["nombre"].split()), "categoria": p.get("categoria"),
        "marca": p.get("marca"), "precio": p.get("precio"), "stock": p.get("stock"),
        "imagen": p.get("imagen"), "url": p.get("url"),
        "atributos": {k: v for k, v in (p.get("atributos") or {}).items() if v is not None},
    }


def armado_publico(config: dict | None) -> dict | None:
    """El armado de PC listo para mostrar y para cargar en la página."""
    if not config:
        return None
    componentes = config.get("componentes") or {}
    reporte = config.get("reporte") or {}
    motivos = armado.motivos_para_no_confirmar(config)
    presupuesto = config.get("presupuesto")
    return {
        "version": config.get("version"),
        "presupuesto": presupuesto,
        "perfil_uso": config.get("perfil_uso"),
        "componentes": [{"lugar": lugar, "cantidad": armado.cantidad(config, lugar), "producto": producto_publico(p)}
                        for lugar, p in componentes.items()],
        "total": config.get("total", 0.0),
        "dentro_del_presupuesto": None if presupuesto is None else config.get("total", 0.0) <= presupuesto,
        "compatibilidad": {
            "estado": reporte.get("estado_general", "sin_verificar"),
            "reglas": [{"regla": r["regla"], "estado": r["estado"], "detalle": r["detalle"],
                        "critica": r.get("critica", True)}
                       for r in reporte.get("resultados", [])],
        },
        # Lo que la página carga en el carrito o en «Armá tu PC» cuando el usuario confirma.
        "pedido": [{"lugar": lugar, "codigo": p["codigo"], "cantidad": armado.cantidad(config, lugar)}
                   for lugar, p in componentes.items()],
        "se_puede_confirmar": not motivos,
        "motivos_para_no_confirmar": motivos,
    }


def eventos_publicos(eventos: Iterable[dict], depurar: bool = False) -> Iterator[dict]:
    """Traduce los eventos internos del agente (agente.eventos) a los que puede recibir la interfaz."""
    llamadas: dict[str, str] = {}   # id del tool call -> nombre de la tool
    for e in eventos:
        tipo = e["tipo"]
        if tipo == "razonamiento":
            if depurar:
                yield {"tipo": "razonamiento", "visibilidad": INTERNO, "texto": e["texto"]}
        elif tipo == "texto":
            yield {"tipo": "texto", "visibilidad": MOSTRAR, "texto": e["texto"]}
        elif tipo == "llamada":
            llamadas[e["id"]] = e["nombre"]
            if e["nombre"] not in SIN_AVISO:
                yield {"tipo": "estado", "visibilidad": OPCIONAL, "paso": e["nombre"],
                       "texto": ESTADOS.get(e["nombre"], "Trabajando…")}
        elif tipo == "resultado":
            yield from _resultado_publico(llamadas.get(e["id"], ""), e.get("datos"))
        elif tipo == "fuentes":
            yield {"tipo": "fuentes", "visibilidad": MOSTRAR,
                   "fuentes": [{"titulo": f["title"], "url": f["url"] if f["url"].startswith("http") else None}
                               for f in e["fuentes"]]}


def _resultado_publico(nombre: str, datos) -> Iterator[dict]:
    """Solo algunos resultados de tools tienen algo para mostrar; el resto es para el modelo."""
    if not isinstance(datos, dict):
        return
    if nombre == "buscar_productos" and datos.get("productos"):
        # Las «notas» de la búsqueda no se envían: son indicaciones para el modelo, no para el cliente.
        yield {"tipo": "productos", "visibilidad": MOSTRAR,
               "productos": [producto_publico(p) for p in datos["productos"]]}
    elif nombre == "obtener_producto" and datos.get("producto"):
        yield {"tipo": "productos", "visibilidad": MOSTRAR, "productos": [producto_publico(datos["producto"])]}
    elif nombre in PREGUNTAS and datos.get("pregunta"):   # botones: preguntar_al_usuario
        yield {"tipo": "pregunta", "visibilidad": MOSTRAR, "pregunta": datos["pregunta"],
               "opciones": datos.get("opciones", [])}
    elif "configuracion" in datos:   # tools de armado
        yield {"tipo": "armado", "visibilidad": MOSTRAR, "armado": armado_publico(datos["configuracion"])}


def _sse(evento: dict) -> str:
    """Un evento en formato Server-Sent Events: nombre del evento + JSON."""
    return f"event: {evento['tipo']}\ndata: {json.dumps(evento, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class PedidoChat(BaseModel):
    mensaje: str = Field(min_length=1, max_length=2000, description="Lo que escribió el usuario")
    conversacion_id: str | None = Field(
        default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$",
        description="Identificador de la conversación. Si no se envía, el servicio crea una nueva.")
    depurar: bool = Field(default=False, description="Pide el razonamiento. Solo con AGENTE_DEPURAR=1.")
    modelo: str | None = Field(
        default=None, min_length=1, max_length=32,
        description="Modelo a usar (por defecto «local»). Se valida contra AGENTE_MODELOS_PERMITIDOS.")


def _lista_modelos_permitidos() -> list[str]:
    """Opciones habilitadas por AGENTE_MODELOS_PERMITIDOS (por defecto solo «local»)."""
    crudo = os.getenv("AGENTE_MODELOS_PERMITIDOS", OPCION_LOCAL)
    return [m.strip() for m in crudo.split(",") if m.strip()] or [OPCION_LOCAL]


def modelos_permitidos() -> dict[str, str]:
    """Modelos permitidos por AGENTE_MODELOS_PERMITIDOS que además están configurados en model.py."""
    disponibles = opciones_de_modelo()
    return {m: disponibles[m] for m in _lista_modelos_permitidos() if m in disponibles}


def validar_modelo(modelo: str | None) -> str:
    """Devuelve la opción de modelo a usar o rechaza el pedido con HTTP 400 antes de ejecutar el turno."""
    opcion = modelo or OPCION_LOCAL
    permitidos = _lista_modelos_permitidos()
    if opcion not in permitidos:
        raise HTTPException(
            status_code=400,
            detail=f"Modelo {opcion!r} no permitido. Permitidos: {', '.join(permitidos)}.",
        )
    disponibles = opciones_de_modelo()
    if opcion not in disponibles:
        raise HTTPException(
            status_code=400,
            detail=f"El modelo {opcion!r} no está configurado en el servidor. "
                   f"Disponibles: {', '.join(disponibles)}.",
        )
    return opcion


def crear_app(agente=None) -> FastAPI:
    """Arma la aplicación. `agente` permite pasar uno de prueba; por defecto usa el de la aplicación."""
    app = FastAPI(title="Asistente de compra AMN", version="0.1.0",
                  description="Servicio del agente. Ver docs/GUIA_INTEGRACION.md.")
    ocupadas: set[str] = set()   # conversaciones con un turno en curso
    candado = threading.Lock()

    def el_agente(opcion: str = OPCION_LOCAL):
        return agente or get_agent(opcion)

    def verificar_clave(x_agente_clave: str | None = Header(default=None)) -> None:
        clave = os.getenv("AGENTE_CLAVE")
        if clave and x_agente_clave != clave:
            raise HTTPException(status_code=401, detail="Falta la cabecera X-Agente-Clave o es incorrecta.")

    def config_de(conversacion_id: str) -> dict:
        return {"configurable": {"thread_id": conversacion_id}}

    @app.get("/salud")
    def salud() -> dict:
        return {"estado": "ok"}

    @app.post("/chat", dependencies=[Depends(verificar_clave)])
    def chat(pedido: PedidoChat) -> StreamingResponse:
        opcion = validar_modelo(pedido.modelo)
        conversacion_id = pedido.conversacion_id or uuid4().hex
        with candado:
            if conversacion_id in ocupadas:
                raise HTTPException(status_code=409, detail="Esa conversación ya tiene una respuesta en curso.")
            ocupadas.add(conversacion_id)
        depurar = pedido.depurar and os.getenv("AGENTE_DEPURAR") == "1"

        def flujo() -> Iterator[str]:
            try:
                yield _sse({"tipo": "inicio", "conversacion_id": conversacion_id})
                config = config_de(conversacion_id)
                agente_turno = el_agente(opcion)
                mensajes = saved_state(config, agente_turno).get("messages", [])
                turno = sum(1 for m in mensajes if m.type == "human") + 1
                internos = stream_turn(pedido.mensaje.strip(), config, turno, agente_turno)
                for evento in eventos_publicos(internos, depurar):
                    yield _sse(evento)
                yield _sse({"tipo": "fin"})
            except Exception:   # el detalle va al registro del servidor, no al cliente
                registro.exception("Falló el turno de la conversación %s", conversacion_id)
                yield _sse({"tipo": "error", "visibilidad": MOSTRAR,
                            "mensaje": "No pude responder en este momento. Probá de nuevo en unos segundos."})
            finally:
                with candado:
                    ocupadas.discard(conversacion_id)

        # Sin caché ni buffer: cada evento tiene que llegar apenas se produce.
        return StreamingResponse(flujo(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

    @app.get("/conversaciones/{conversacion_id}", dependencies=[Depends(verificar_clave)])
    def conversacion(conversacion_id: str) -> dict:
        config = config_de(conversacion_id)
        turnos = [{"usuario": pregunta, "eventos": list(eventos_publicos(eventos))}
                  for pregunta, eventos in saved_turns(config, el_agente())]
        estado = saved_state(config, el_agente())
        return {"conversacion_id": conversacion_id, "turnos": turnos,
                "armado": armado_publico(estado.get("configuracion"))}

    return app


app = crear_app()
