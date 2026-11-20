"""Problema 24: el modelo escribe la llamada a una tool como texto JSON en vez de ejecutarla.

Prueba el detector, la métrica por conversación y el middleware que reintenta una vez.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import agente as modulo_agente
from agente import (
    crear_agente,
    crear_checkpointer,
    llamada_como_texto,
    llamadas_a_tools,
    llamadas_como_texto,
    new_thread,
    saved_state,
    stream_turn,
)
from tests.falsos import ModeloFalso, llamada, texto


class ModeloQueAnota(ModeloFalso):
    """Modelo falso que guarda los mensajes recibidos en cada llamada."""
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


@pytest.mark.parametrize("respuesta, tool_esperada", [
    ('{"todos": [{"task": "Elegir CPU", "status": "pending"}]}', "write_todos"),
    ('{"presupuesto": 2800000, "perfil_uso": "juegos 1080p"}', "iniciar_configuracion"),
    ('{"lugar": "cpu", "codigo": "CPU002"}', "agregar_o_reemplazar_componente"),
    ('{"categoria": "cpu", "gama": "media", "limite": 5}', "buscar_productos"),
    ('{"lugar": "ram"}', "buscar_pieza_armado"),
    ('{"pregunta": "¿Intel o AMD?", "opciones": ["Intel", "AMD"]}', "preguntar_al_usuario"),
    ('```json\n{"name": "buscar_productos", "arguments": {"categoria": "gpu"}}\n```', "buscar_productos"),
    ('<tool_call>\n{"name": "iniciar_configuracion", "arguments": {"presupuesto": 1200000}}\n</tool_call>',
     "iniciar_configuracion"),
])
def test_detecta_llamada_escrita_como_texto(respuesta, tool_esperada):
    assert llamada_como_texto(respuesta) == tool_esperada


@pytest.mark.parametrize("respuesta", [
    "Te recomiendo el CPU AMD Ryzen 5 5500 a $ 149.950 (stock 4).",
    "Una PC de gama media ronda los $ 2.762.000.",
    '{"precio": 150000, "moneda": "ARS"}',
    "Acá tenés las opciones para elegir.",
])
def test_no_marca_texto_comun_ni_json_ajeno(respuesta):
    assert llamada_como_texto(respuesta) is None


def test_metrica_cuenta_llamadas_como_texto_y_las_marca_como_error():
    mensajes = [
        HumanMessage("Armame una PC"),
        llamada("load_skill", {"nombre": "armado_pc"}, "c1"),
        ToolMessage("ok", tool_call_id="c1"),
        AIMessage(content='pensé</think>{"todos": [{"task": "Elegir CPU", "status": "pending"}]}'),
        HumanMessage("Seguí"),
        AIMessage(content="¿Para qué la vas a usar?"),
    ]
    fallas = llamadas_como_texto(mensajes)
    assert len(fallas) == 1
    assert fallas[0]["turno"] == 1 and fallas[0]["tool"] == "write_todos"

    registro = llamadas_a_tools(mensajes)
    assert any(r["tool"] == "write_todos" and r["error"] is True for r in registro)


def test_middleware_reintenta_una_vez_y_ejecuta_la_tool(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        texto('pensé</think>{"todos": [{"task": "Elegir CPU", "status": "pending"}]}'),
        llamada("write_todos", {"todos": [{"task": "Elegir CPU", "status": "pending"}]}),
        texto("Ya armé el plan."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()
    list(stream_turn("Planificá una compra de periféricos", config, 1, agente))

    assert len(modelo.recibidos) == 3
    assert "tool calling" in modelo.recibidos[1][-1].text
    guardados = saved_state(config, agente)["messages"]
    assert [m.type for m in guardados] == ["human", "ai", "tool", "ai"]
    assert not any('"todos"' in m.text and not getattr(m, "tool_calls", None) for m in guardados)


def test_middleware_reintenta_una_sola_vez_si_insiste(cliente, tmp_path):
    json_suelto = '{"todos": [{"task": "Elegir CPU", "status": "pending"}]}'
    modelo = ModeloQueAnota(messages=iter([texto(json_suelto), texto(json_suelto)]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()
    list(stream_turn("Planificá una compra de periféricos", config, 1, agente))
    assert len(modelo.recibidos) == 2
    assert saved_state(config, agente)["messages"][-1].text == json_suelto


def test_texto_normal_no_dispara_reintento(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([texto("Contame para qué la vas a usar.")]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    list(stream_turn("Hola", new_thread(), 1, agente))
    assert len(modelo.recibidos) == 1
