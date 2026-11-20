"""Servicio HTTP del agente: qué eventos salen hacia la página y cuáles no.

El agente corre con un modelo falso (respuestas fijas) contra el servidor MCP real de la tienda
sobre el catálogo de prueba, así que se prueba todo el recorrido sin un LLM.
"""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from agente import crear_agente
from servicio import armado_publico, crear_app, eventos_publicos
from tests.falsos import buscar, llamada, modelo_con, texto


def _cliente_http(cliente, *mensajes: AIMessage) -> TestClient:
    agente = crear_agente(modelo=modelo_con(*mensajes), cliente=cliente, checkpointer=InMemorySaver())
    return TestClient(crear_app(agente))


def _eventos(respuesta) -> list[dict]:
    """Interpreta el cuerpo text/event-stream: una lista de eventos con su tipo."""
    eventos = []
    for bloque in respuesta.text.strip().split("\n\n"):
        nombre, datos = bloque.split("\n", 1)
        evento = json.loads(datos.removeprefix("data: "))
        assert nombre == f"event: {evento['tipo']}"
        eventos.append(evento)
    return eventos


def _chat(http: TestClient, mensaje: str, conversacion_id: str | None = None, **extra) -> list[dict]:
    respuesta = http.post("/chat", json={"mensaje": mensaje, "conversacion_id": conversacion_id, **extra})
    assert respuesta.status_code == 200 and respuesta.headers["content-type"].startswith("text/event-stream")
    return _eventos(respuesta)


def _codigo(cliente, categoria: str) -> str:
    _, datos = cliente.llamar_json("buscar_productos", categoria=categoria, limite=1)
    return datos["productos"][0]["codigo"]


def test_busqueda_emite_estado_productos_y_texto(cliente):
    http = _cliente_http(
        cliente,
        llamada("buscar_productos", {"categoria": "cables", "atributos": {"conector_a": "HDMI", "largo_m": 2}}),
        texto("Te recomiendo el CAB002."),
    )
    eventos = _chat(http, "Necesito un cable HDMI de 2 metros")
    assert [e["tipo"] for e in eventos] == ["inicio", "estado", "productos", "texto", "fin"]
    assert eventos[0]["conversacion_id"]
    estado, productos = eventos[1], eventos[2]
    # El aviso dice qué está haciendo, pero no con qué argumentos llamó a la tool.
    assert estado == {"tipo": "estado", "visibilidad": "opcional", "paso": "buscar_productos",
                      "texto": "Buscando productos…"}
    assert "CAB002" in [p["codigo"] for p in productos["productos"]]
    assert set(productos["productos"][0]) == {"codigo", "nombre", "categoria", "marca", "precio", "stock", "imagen",
                                              "url", "atributos"}   # sin descripción ni campos internos
    assert "notas" not in productos   # las notas de la búsqueda son indicaciones para el modelo
    assert eventos[3]["texto"] == "Te recomiendo el CAB002."


def test_armado_emite_el_pedido_para_cargar_en_la_pagina(cliente):
    cpu = _codigo(cliente, "cpu")
    http = _cliente_http(
        cliente,
        llamada("iniciar_configuracion", {"presupuesto": 900000, "perfil_uso": "oficina"}, "c1"),
        buscar("cpu"),
        llamada("agregar_o_reemplazar_componente", {"lugar": "cpu", "codigo": cpu}, "c2"),
        texto("Ya puse el procesador."),
    )
    eventos = _chat(http, "Armame una PC de oficina", "conv-armado")
    armados = [e["armado"] for e in eventos if e["tipo"] == "armado"]
    assert len(armados) == 2 and armados[0]["componentes"] == []
    final = armados[-1]
    assert final["pedido"] == [{"lugar": "cpu", "codigo": cpu, "cantidad": 1}]
    assert final["componentes"][0]["producto"]["codigo"] == cpu and final["total"] > 0
    assert final["presupuesto"] == 900000 and final["dentro_del_presupuesto"] is True
    # Con una sola pieza faltan las demás: la página no tiene que habilitar «Confirmar».
    assert final["se_puede_confirmar"] is False and "Faltan piezas" in final["motivos_para_no_confirmar"][0]
    assert final["compatibilidad"]["estado"] in ("compatible", "incompatible", "sin_confirmar")

    # Reabrir el chat: el historial y el armado se recuperan con el mismo formato.
    guardada = http.get("/conversaciones/conv-armado").json()
    assert guardada["armado"]["pedido"] == final["pedido"]
    assert guardada["turnos"][0]["usuario"] == "Armame una PC de oficina"
    assert [e["tipo"] for e in guardada["turnos"][0]["eventos"]] == [e["tipo"] for e in eventos[1:-1]]


def test_pregunta_con_opciones_termina_el_turno(cliente):
    # El modelo falso tiene una sola respuesta: si el agente lo volviera a consultar, el turno fallaría.
    http = _cliente_http(
        cliente, llamada("preguntar_al_usuario", {"pregunta": "¿Intel o AMD?", "opciones": ["Intel", "AMD", "AMD "]}))
    eventos = _chat(http, "Quiero armar una PC")
    assert [e["tipo"] for e in eventos] == ["inicio", "pregunta", "fin"]
    assert eventos[1] == {"tipo": "pregunta", "visibilidad": "mostrar", "pregunta": "¿Intel o AMD?",
                          "opciones": ["Intel", "AMD"]}


def test_la_conversacion_sigue_en_el_segundo_turno(cliente):
    http = _cliente_http(cliente, texto("Hola, ¿qué buscás?"), texto("Perfecto."))
    primero = _chat(http, "hola")
    conversacion_id = primero[0]["conversacion_id"]
    segundo = _chat(http, "una notebook", conversacion_id)
    assert segundo[0]["conversacion_id"] == conversacion_id
    turnos = http.get(f"/conversaciones/{conversacion_id}").json()["turnos"]
    assert [t["usuario"] for t in turnos] == ["hola", "una notebook"]


def test_un_error_interno_no_muestra_detalles(cliente):
    http = _cliente_http(cliente)   # modelo sin respuestas: el turno falla por dentro
    eventos = _chat(http, "hola")
    assert [e["tipo"] for e in eventos] == ["inicio", "error"]
    assert "Traceback" not in eventos[1]["mensaje"] and "StopIteration" not in eventos[1]["mensaje"]


def test_el_razonamiento_solo_sale_en_modo_depuracion(cliente, monkeypatch):
    internos = [{"tipo": "razonamiento", "texto": "pienso..."}, {"tipo": "texto", "texto": "Hola"},
                {"tipo": "llamada", "id": "c1", "nombre": "write_todos", "args": {"todos": []}},
                {"tipo": "resultado", "id": "c1", "texto": "ok", "datos": None}]
    assert [e["tipo"] for e in eventos_publicos(internos)] == ["texto"]   # ni razonamiento ni TODOs
    assert [e["tipo"] for e in eventos_publicos(internos, depurar=True)] == ["razonamiento", "texto"]

    # Aunque el pedido lo solicite, sin AGENTE_DEPURAR=1 en el servidor no se emite.
    monkeypatch.delenv("AGENTE_DEPURAR", raising=False)
    http = _cliente_http(cliente, AIMessage(content="Hola", additional_kwargs={"reasoning_content": "pienso..."}))
    assert "razonamiento" not in [e["tipo"] for e in _chat(http, "hola", depurar=True)]
    monkeypatch.setenv("AGENTE_DEPURAR", "1")
    http = _cliente_http(cliente, AIMessage(content="Hola", additional_kwargs={"reasoning_content": "pienso..."}))
    assert "razonamiento" in [e["tipo"] for e in _chat(http, "hola", depurar=True)]


def test_el_razonamiento_dentro_del_texto_no_llega_al_cliente(cliente):
    # Algunos modelos locales dejan lo que pensaron en el contenido, cerrado con </think>.
    crudo = "Okay, the user wants a cable. Let me think...\n</think>\n\n¡Hola! ¿Qué buscás?"
    http = _cliente_http(cliente, texto(crudo))
    eventos = _chat(http, "hola")
    assert [e["tipo"] for e in eventos] == ["inicio", "texto", "fin"]
    assert eventos[1]["texto"] == "¡Hola! ¿Qué buscás?"


def test_clave_del_servicio(cliente, monkeypatch):
    monkeypatch.setenv("AGENTE_CLAVE", "secreta")
    http = _cliente_http(cliente, texto("Hola"))
    assert http.post("/chat", json={"mensaje": "hola"}).status_code == 401
    assert http.get("/conversaciones/x").status_code == 401
    assert http.get("/salud").status_code == 200   # la prueba de vida no pide clave
    assert http.post("/chat", json={"mensaje": "hola"}, headers={"X-Agente-Clave": "secreta"}).status_code == 200


@pytest.mark.parametrize("cuerpo", [{"mensaje": ""}, {"mensaje": "x" * 2001},
                                    {"mensaje": "hola", "conversacion_id": "../otra"}])
def test_pedidos_invalidos(cliente, cuerpo):
    assert _cliente_http(cliente).post("/chat", json=cuerpo).status_code == 422


def test_armado_publico_vacio():
    assert armado_publico(None) is None and armado_publico({}) is None


def test_los_avisos_de_estado_son_los_que_se_muestran_en_el_chat():
    """Lo que ve el cliente mientras el agente trabaja: qué hace, sin razonamiento ni argumentos."""
    from servicio import ESTADOS
    assert ESTADOS["buscar_productos"] == "Buscando productos…"
    assert ESTADOS["buscar_especificaciones_web"] == "Buscando en internet…"
    assert ESTADOS["buscar_pieza_armado"] == "Buscando piezas para el armado…"


def test_modelo_ausente_usa_local(cliente, monkeypatch):
    import servicio

    monkeypatch.delenv("AGENTE_MODELOS_PERMITIDOS", raising=False)
    elegidos: list[str] = []
    memoria = InMemorySaver()
    agente_local = crear_agente(modelo=modelo_con(texto("Respuesta local.")), cliente=cliente, checkpointer=memoria)

    def _get_agent(opcion="local"):
        elegidos.append(opcion)
        return agente_local

    monkeypatch.setattr(servicio, "get_agent", _get_agent)
    http = TestClient(crear_app())
    eventos = _chat(http, "hola")
    assert elegidos == ["local"]
    assert [e["tipo"] for e in eventos] == ["inicio", "texto", "fin"]
    assert eventos[1]["texto"] == "Respuesta local."


def test_modelo_permitido_elige_ese_agente(cliente, monkeypatch):
    import servicio

    monkeypatch.setenv("AGENTE_MODELOS_PERMITIDOS", "local, gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-de-prueba")
    elegidos: list[str] = []
    memoria = InMemorySaver()
    agentes = {
        "local": crear_agente(modelo=modelo_con(texto("Desde local.")), cliente=cliente, checkpointer=memoria),
        "gemini": crear_agente(modelo=modelo_con(texto("Desde Gemini.")), cliente=cliente, checkpointer=memoria),
    }

    def _get_agent(opcion="local"):
        elegidos.append(opcion)
        return agentes[opcion]

    monkeypatch.setattr(servicio, "get_agent", _get_agent)
    http = TestClient(crear_app())

    ev_gemini = _chat(http, "hola", "conv-modelo", modelo="gemini")
    assert ev_gemini[1]["texto"] == "Desde Gemini."
    ev_local = _chat(http, "seguimos", "conv-modelo", modelo="local")
    assert ev_local[1]["texto"] == "Desde local."
    assert elegidos == ["gemini", "local"]


def test_modelo_no_permitido_rechaza_sin_ejecutar_el_turno(cliente, monkeypatch):
    import servicio

    elegidos: list[str] = []
    monkeypatch.setattr(servicio, "get_agent", lambda opcion="local": elegidos.append(opcion))
    http = TestClient(crear_app())

    # Por defecto solo se permite «local».
    monkeypatch.delenv("AGENTE_MODELOS_PERMITIDOS", raising=False)
    r = http.post("/chat", json={"mensaje": "hola", "modelo": "gemini"})
    assert r.status_code == 400
    assert "no permitido" in r.json()["detail"].lower()
    assert elegidos == []

    # Permitido en la variable pero desconocido / no permitido explícitamente.
    monkeypatch.setenv("AGENTE_MODELOS_PERMITIDOS", "local,gemini")
    r_otro = http.post("/chat", json={"mensaje": "hola", "modelo": "otro"})
    assert r_otro.status_code == 400
    assert "no permitido" in r_otro.json()["detail"].lower()
    assert elegidos == []

    # Permitido en la variable pero sin configurar en el .env (faltan GOOGLE_API_KEY / GEMINI_MODEL).
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    r_sin_config = http.post("/chat", json={"mensaje": "hola", "modelo": "gemini"})
    assert r_sin_config.status_code == 400
    assert "no está configurado" in r_sin_config.json()["detail"].lower()
    assert elegidos == []


def test_siguiente_pregunta_armado_no_emite_estado_ni_pregunta(cliente):
    """Versión 1 de la entrevista: solo preguntar_al_usuario emite el evento `pregunta` al cliente."""
    internos = [
        {"tipo": "llamada", "id": "e1", "nombre": "siguiente_pregunta_armado", "args": {}},
        {"tipo": "resultado", "id": "e1", "texto": "{}", "datos": {"pregunta": "ignorar", "opciones": ["A", "B"]}},
    ]
    assert list(eventos_publicos(internos)) == []

    http = _cliente_http(
        cliente,
        llamada("siguiente_pregunta_armado", {}, "e1"),
        llamada("preguntar_al_usuario", {"pregunta": "¿Para qué la vas a usar?",
                                         "opciones": ["Oficina o estudio", "Jugar"]}, "p1"),
    )
    eventos = _chat(http, "Quiero armar una PC")
    assert [e["tipo"] for e in eventos] == ["inicio", "pregunta", "fin"]
    assert eventos[1] == {"tipo": "pregunta", "visibilidad": "mostrar", "pregunta": "¿Para qué la vas a usar?",
                          "opciones": ["Oficina o estudio", "Jugar"]}


def test_buscar_pieza_armado_emite_estado_y_productos(cliente):
    from mcp_tienda.armado.entrevista import siguiente

    perfil = siguiente({"uso": "Oficina o estudio", "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})[
        "perfil"
    ]
    memoria = InMemorySaver()
    agente = crear_agente(
        modelo=modelo_con(llamada("buscar_pieza_armado", {"lugar": "cpu"}, "bp1"), texto("Te recomiendo este CPU.")),
        cliente=cliente,
        checkpointer=memoria,
    )
    config = {"configurable": {"thread_id": "conv-pieza-armado"}}
    agente.update_state(config, {"entrevista": {"respuestas": {}, "pendiente": None, "perfil": perfil}})
    http = TestClient(crear_app(agente))

    eventos = _chat(http, "Buscá un procesador", "conv-pieza-armado")
    assert [e["tipo"] for e in eventos] == ["inicio", "estado", "productos", "texto", "fin"]
    assert eventos[1] == {"tipo": "estado", "visibilidad": "opcional", "paso": "buscar_pieza_armado",
                          "texto": "Buscando piezas para el armado…"}
    assert eventos[2]["productos"]
    assert all(p["categoria"] == "cpu" for p in eventos[2]["productos"])
    assert set(eventos[2]["productos"][0]) == {"codigo", "nombre", "categoria", "marca", "precio", "stock",
                                               "imagen", "url", "atributos"}
