"""Problema 20: el modelo afirma una acción («agregué», «buscando…») sin haber llamado a la tool.

C: el detector y la métrica por conversación. B: el middleware que le pide al modelo, una sola vez,
que llame a la tool o corrija lo que dijo.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import agente as modulo_agente
from agente import (
    accion_sin_respaldo,
    afirmaciones_sin_respaldo,
    crear_agente,
    crear_checkpointer,
    new_thread,
    saved_state,
    stream_turn,
)
from tests.falsos import ModeloFalso, llamada, texto


class ModeloQueAnota(ModeloFalso):
    """Modelo falso que guarda los mensajes que recibe en cada llamada."""
    recibidos: list = []

    def _generate(self, messages, *args, **kwargs):
        self.recibidos.append(list(messages))
        return super()._generate(messages, *args, **kwargs)

    def _stream(self, messages, *args, **kwargs):
        self.recibidos.append(list(messages))
        yield from super()._stream(messages, *args, **kwargs)


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo_agente, "CONV_FILE", tmp_path / "conversaciones.txt")


# --- C: detector -----------------------------------------------------------------

@pytest.mark.parametrize("respuesta, tipo", [
    # los tres casos reales de la conversación 99c1a78e
    ("¡Listo! Agregué el procesador Intel i5-12400F. Ahora seleccionamos la tarjeta gráfica para jugar. 🎮", "armado"),
    ('¡Agregué el procesador en la sección "procesador"! Ahora seleccionamos la tarjeta gráfica.', "armado"),
    ("¡Listo! Buscando tarjetas gráficas para jugar... 🔍", "busqueda"),
    ("Cambié la placa de video por una RTX 4060.", "armado"),
    ("Voy a buscar fuentes de 650 W.", "busqueda"),
])
def test_detecta_acciones_afirmadas_sin_tool(respuesta, tipo):
    assert accion_sin_respaldo(respuesta, tools_del_turno=set()) == tipo


@pytest.mark.parametrize("respuesta", [
    "Todavía no agregué la RAM: primero elegí el procesador.",
    "No cambié nada del armado.",
    "¿Querés que busque una placa de video?",
    "El armado tiene procesador y placa madre.",
])
def test_no_marca_negaciones_ni_preguntas(respuesta):
    assert accion_sin_respaldo(respuesta, tools_del_turno=set()) is None


def test_no_marca_si_la_tool_se_llamo_en_el_turno():
    assert accion_sin_respaldo("Agregué el procesador.", {"agregar_o_reemplazar_componente"}) is None
    assert accion_sin_respaldo("Buscando placas de video…", {"buscar_productos"}) is None
    # buscar no respalda «agregué»
    assert accion_sin_respaldo("Agregué el procesador.", {"buscar_productos"}) == "armado"


def test_metrica_por_conversacion_cuenta_por_turno():
    mensajes = [
        HumanMessage("Agregá el CPU001"),
        llamada("agregar_o_reemplazar_componente", {"lugar": "cpu", "codigo": "CPU001"}),
        ToolMessage("{}", tool_call_id="c1"),
        AIMessage(content="pensé</think>Agregué el procesador CPU001."),      # respaldada
        HumanMessage("Sí"),
        AIMessage(content="pensé</think>¡Listo! Agregué la placa de video."),  # sin respaldo
    ]
    [falla] = afirmaciones_sin_respaldo(mensajes)
    assert falla["turno"] == 2 and falla["tipo"] == "armado" and falla["respuesta"].startswith("¡Listo!")


# --- B: middleware -----------------------------------------------------------------

def test_si_afirma_sin_tool_se_le_pide_una_vez_y_llama_a_la_tool(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        texto("pensé</think>¡Listo! Agregué el procesador."),       # 1.ª: afirma sin tool
        llamada("read_todos", {}),                                   # reintento: llama a una tool
        texto("Todavía no hay plan."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()
    list(stream_turn("Sí, agregalo", config, 1, agente))

    assert len(modelo.recibidos) == 3
    reintento = modelo.recibidos[1]
    assert "llamá a la tool" in reintento[-1].text            # el aviso va solo en la copia del reintento
    guardados = saved_state(config, agente)["messages"]
    assert [m.type for m in guardados] == ["human", "ai", "tool", "ai"]   # la afirmación falsa no quedó
    assert not any("Agregué" in m.text for m in guardados)


def test_reintenta_una_sola_vez(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        texto("¡Listo! Agregué el procesador."),
        texto("Ya agregué el procesador, quedó en el armado."),     # insiste: no hay segundo reintento
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()
    list(stream_turn("Sí", config, 1, agente))
    assert len(modelo.recibidos) == 2
    assert saved_state(config, agente)["messages"][-1].text == "Ya agregué el procesador, quedó en el armado."


def test_sin_afirmacion_no_hay_reintento(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([texto("¿Qué presupuesto tenés?")]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    list(stream_turn("Quiero una PC", new_thread(), 1, agente))
    assert len(modelo.recibidos) == 1
