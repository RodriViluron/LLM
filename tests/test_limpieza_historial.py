"""Problema 23: el razonamiento viejo no se le reenvía al modelo, pero sigue guardado para la pantalla."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import agente as modulo_agente
from agente import (
    crear_agente,
    crear_checkpointer,
    limpiar_historial_para_el_modelo,
    new_thread,
    saved_state,
    saved_turns,
    stream_turn,
)
from tests.falsos import ModeloFalso, texto

PENSADO = "Okay, the user wants a PC. Let me think about it."


class ModeloQueAnota(ModeloFalso):
    """Modelo falso que guarda los mensajes que recibe en cada llamada."""
    recibidos: list = []

    def _generate(self, messages, *args, **kwargs):
        self.recibidos.append(list(messages))
        return super()._generate(messages, *args, **kwargs)

    def _stream(self, messages, *args, **kwargs):   # el agente puede llamarlo en modo streaming
        self.recibidos.append(list(messages))
        yield from super()._stream(messages, *args, **kwargs)


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo_agente, "CONV_FILE", tmp_path / "conversaciones.txt")


def test_respuesta_final_queda_sin_razonamiento():
    m = AIMessage(content=f"{PENSADO}</think>¡Hola! ¿Qué presupuesto tenés?", id="a1")
    [limpio] = limpiar_historial_para_el_modelo([m])
    assert limpio.content == "¡Hola! ¿Qué presupuesto tenés?"
    assert limpio.id == "a1"
    assert m.content.startswith(PENSADO)          # el original no se toca


def test_llamada_a_tool_queda_sin_texto_aunque_no_cierre_el_think():
    """qwen3 a veces llama a la tool sin cerrar </think>: todo el texto es razonamiento."""
    con_cierre = AIMessage(content=f"{PENSADO}</think>", tool_calls=[{"name": "read_todos", "args": {}, "id": "c1"}])
    sin_cierre = AIMessage(content=PENSADO, tool_calls=[{"name": "read_todos", "args": {}, "id": "c2"}])
    limpios = limpiar_historial_para_el_modelo([con_cierre, sin_cierre])
    assert [m.content for m in limpios] == ["", ""]
    assert [m.tool_calls[0]["id"] for m in limpios] == ["c1", "c2"]   # la llamada se conserva


def test_no_toca_mensajes_del_usuario_ni_de_tools_ni_respuestas_sin_razonamiento():
    mensajes = [HumanMessage("hola </think>"), ToolMessage("dato", tool_call_id="c1"), AIMessage(content="Listo.")]
    assert limpiar_historial_para_el_modelo(mensajes) == mensajes


def test_contenido_en_bloques_no_se_toca():
    """Gemini devuelve el contenido como lista de bloques (con firmas): no se modifica."""
    m = AIMessage(content=[{"type": "text", "text": "Hola"}],
                  tool_calls=[{"name": "read_todos", "args": {}, "id": "c1"}])
    assert limpiar_historial_para_el_modelo([m]) == [m]


def test_el_modelo_no_recibe_el_razonamiento_pero_la_memoria_lo_conserva(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        AIMessage(content=f"{PENSADO}</think>", tool_calls=[{"name": "read_todos", "args": {}, "id": "c1"}]),
        texto(f"{PENSADO}</think>Todavía no hay plan."),
        texto(f"{PENSADO}</think>Arrancamos."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()
    list(stream_turn("¿Qué falta?", config, 1, agente))
    list(stream_turn("Dale", config, 2, agente))

    # Lo que leyó el modelo en cada llamada: nunca el razonamiento de antes.
    assert len(modelo.recibidos) == 3
    for llamada_al_modelo in modelo.recibidos:
        for m in llamada_al_modelo:
            assert PENSADO not in m.text and "</think>" not in m.text
    ultima = modelo.recibidos[-1]
    assert [m.text for m in ultima if m.type == "ai"] == ["", "Todavía no hay plan."]

    # Lo guardado sigue completo: la interfaz muestra el razonamiento.
    guardados = [m for m in saved_state(config, agente)["messages"] if m.type == "ai"]
    assert all(m.text.startswith(PENSADO) for m in guardados)
    eventos_turno_1 = saved_turns(config, agente)[0][1]
    assert [e["tipo"] for e in eventos_turno_1] == ["razonamiento", "llamada", "resultado", "razonamiento", "texto"]
