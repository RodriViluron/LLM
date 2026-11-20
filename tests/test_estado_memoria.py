"""Paso 2: estado propio, memoria con SqliteSaver, TODOs, skills y eventos (patrón de la cátedra)."""

import pytest

import agente as modulo_agente
import tools
from agente import (
    crear_agente,
    crear_checkpointer,
    list_threads,
    new_thread,
    resume_thread,
    saved_state,
    saved_turns,
    select_thread,
    stream_turn,
)
from tests.falsos import llamada, modelo_con, texto

TODOS = [{"task": "Elegir CPU y placa", "status": "in_progress"}, {"task": "Elegir fuente", "status": "pending"}]


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    """Las conversaciones de los tests no tocan conversaciones.txt del proyecto."""
    monkeypatch.setattr(modulo_agente, "CONV_FILE", tmp_path / "conversaciones.txt")


def test_los_todos_y_los_mensajes_sobreviven_a_reabrir_la_memoria(cliente, tmp_path):
    ruta = tmp_path / "memoria.db"
    config = new_thread()

    # Turno 1: el agente escribe el plan. Lo ejecuta una «sesión» del programa.
    agente_1 = crear_agente(modelo_con(llamada("write_todos", {"todos": TODOS}), texto("Plan armado.")),
                            cliente, crear_checkpointer(ruta))
    evs = list(stream_turn("Armame una PC", config, 1, agente_1))
    assert [e["tipo"] for e in evs] == ["llamada", "resultado", "texto"]
    assert evs[1]["texto"] == "TODOs actualizados (2 items)."

    # Se «cierra el programa»: agente nuevo y conexión nueva sobre el mismo archivo.
    agente_2 = crear_agente(modelo_con(llamada("read_todos", {}), texto("Seguimos con la fuente.")),
                            cliente, crear_checkpointer(ruta))
    estado = saved_state(config, agente_2)
    assert estado["todos"] == TODOS
    assert [m.type for m in estado["messages"]] == ["human", "ai", "tool", "ai"]

    # Turno 2: read_todos lee del estado lo que se escribió en el turno 1.
    evs = list(stream_turn("¿Qué falta?", config, 2, agente_2))
    resultado = next(e for e in evs if e["tipo"] == "resultado")
    assert resultado["texto"] == "[in_progress] Elegir CPU y placa\n[pending] Elegir fuente"

    turnos = saved_turns(config, agente_2)
    assert [pregunta for pregunta, _ in turnos] == ["Armame una PC", "¿Qué falta?"]
    assert [e["tipo"] for e in turnos[1][1]] == ["llamada", "resultado", "texto"]


def test_cambiar_de_modelo_en_medio_de_la_conversacion_conserva_el_estado(cliente, tmp_path):
    """Selector de modelo: dos agentes (uno por modelo) sobre la misma memoria."""
    from langchain_core.messages import AIMessage

    memoria = crear_checkpointer(tmp_path / "memoria.db")
    config = new_thread()

    respuesta_a = AIMessage(content="Plan armado.", response_metadata={"model_name": "modelo-a"})
    agente_a = crear_agente(modelo_con(llamada("write_todos", {"todos": TODOS}), respuesta_a), cliente, memoria)
    evs = list(stream_turn("Armame una PC", config, 1, agente_a))
    assert evs[-1] == {"tipo": "texto", "texto": "Plan armado.", "modelo": "modelo-a"}

    # Turno 2 con el otro modelo: ve los TODOs y los mensajes que dejó el primero.
    respuesta_b = AIMessage(content="Sigo con la fuente.", response_metadata={"model": "modelo-b"})
    agente_b = crear_agente(modelo_con(llamada("read_todos", {}), respuesta_b), cliente, memoria)
    evs = list(stream_turn("¿Qué falta?", config, 2, agente_b))
    assert next(e for e in evs if e["tipo"] == "resultado")["texto"].startswith("[in_progress] Elegir CPU")
    assert evs[-1]["modelo"] == "modelo-b"

    # El historial guarda qué modelo escribió cada respuesta.
    turnos = saved_turns(config, agente_a)
    assert [e["modelo"] for _, evs in turnos for e in evs if e["tipo"] == "texto"] == ["modelo-a", "modelo-b"]


def test_get_agent_arma_uno_por_modelo_con_la_misma_memoria(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo_agente, "get_model", lambda opcion: f"modelo {opcion}")
    monkeypatch.setattr(modulo_agente, "crear_checkpointer", lambda: f"memoria en {tmp_path}")
    monkeypatch.setattr(modulo_agente, "crear_agente", lambda modelo, checkpointer: (modelo, checkpointer))
    modulo_agente._agente_de.cache_clear()
    modulo_agente._checkpointer_app.cache_clear()
    try:
        local, gemini = modulo_agente.get_agent("local"), modulo_agente.get_agent("gemini")
        assert local == ("modelo local", f"memoria en {tmp_path}")
        assert gemini == ("modelo gemini", f"memoria en {tmp_path}")   # misma memoria
        assert modulo_agente.get_agent("local") is local               # se arma una sola vez
        assert modulo_agente.get_agent() is local                      # por defecto, el local
    finally:
        modulo_agente._agente_de.cache_clear()
        modulo_agente._checkpointer_app.cache_clear()


def test_mensaje_de_error_de_cuota_es_claro():
    assert "límite de uso" in modulo_agente.mensaje_de_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert "saturado" in modulo_agente.mensaje_de_error(RuntimeError("503 UNAVAILABLE. high demand"))
    assert modulo_agente.mensaje_de_error(RuntimeError("otra cosa")) == "El asistente falló: otra cosa"


def test_conversaciones_separadas_no_comparten_estado(cliente, tmp_path):
    saver = crear_checkpointer(tmp_path / "memoria.db")
    agente = crear_agente(modelo_con(llamada("write_todos", {"todos": TODOS}), texto("ok"), texto("hola")),
                          cliente, saver)
    conversacion_a = new_thread()
    list(stream_turn("Armame una PC", conversacion_a, 1, agente))
    conversacion_b = new_thread()
    list(stream_turn("Hola", conversacion_b, 1, agente))

    assert saved_state(conversacion_a, agente)["todos"] == TODOS
    assert "todos" not in saved_state(conversacion_b, agente)
    # La más reciente primero; el título es el primer mensaje.
    assert [titulo for _, titulo in list_threads(agente=agente)] == ["Hola", "Armame una PC"]
    # Volver a una conversación anterior la deja como activa.
    select_thread(conversacion_a["configurable"]["thread_id"])
    assert resume_thread() == conversacion_a


def test_sin_memoria_cada_invocacion_arranca_de_cero(cliente):
    """Así lo usa la evaluación: un pedido, una conversación."""
    agente = crear_agente(modelo_con(llamada("write_todos", {"todos": TODOS}), texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "Armame una PC")]}, context=tools.Context(turn=1))
    assert resultado["todos"] == TODOS


def test_eventos_llevan_el_artifact_y_el_modelo_no_lo_recibe(cliente):
    @tools.tool
    def con_datos(runtime: tools.ToolRuntime[tools.Context]) -> tools.Command:
        """Tool de prueba que manda datos a la interfaz."""
        return tools._respond(runtime, "resumen corto", artifact={"producto": {"codigo": "CAB002"}})

    from langchain.agents import create_agent

    agente = create_agent(modelo_con(llamada("con_datos", {}), texto("listo")), tools=[con_datos],
                          state_schema=tools.EstadoTienda, context_schema=tools.Context)
    mensajes = agente.invoke({"messages": [("user", "x")]}, context=tools.Context(turn=1))["messages"]
    resultado = next(e for e in modulo_agente.eventos(mensajes) if e["tipo"] == "resultado")
    assert resultado["texto"] == "resumen corto"                      # lo que lee el modelo
    assert resultado["datos"] == {"producto": {"codigo": "CAB002"}}   # lo que recibe la interfaz


def test_fuentes_no_se_repiten_dentro_de_un_turno():
    a = {"turn": 1, "url": "https://x", "title": "X"}
    b = {"turn": 2, "url": "https://x", "title": "X"}
    assert tools._merge_sources([a], [dict(a), b]) == [a, b]


def test_load_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "SKILLS_DIR", tmp_path)
    skill = "---\ndescription: Cómo armar una PC.\n---\n# Skill\nPaso 1"
    (tmp_path / "armado_pc.md").write_text(skill, encoding="utf-8")
    assert tools.listar_skills() == "armado_pc: Cómo armar una PC."
    assert "Paso 1" in tools.load_skill.invoke({"nombre": "armado_pc"})
    assert "Disponibles: armado_pc" in tools.load_skill.invoke({"nombre": "latex"})


def test_el_prompt_menciona_todos_y_skills():
    prompt = modulo_agente.construir_prompt()
    assert "write_todos" in prompt and "load_skill" in prompt
