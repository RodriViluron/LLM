"""Problema 20: agregar_o_reemplazar_componente solo acepta códigos que ya aparecieron en la conversación.

El modelo llegó a pasar códigos inventados con el formato del catálogo («CPU001») o adivinados desde su
conocimiento general (en el catálogo real los códigos son modelos, como «12400F»). La tool los rechaza si
no salieron de una búsqueda.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agente import crear_agente
from tests.falsos import buscar, llamada, modelo_con, texto
from tools import Context, codigo_visto


def _resultado_de(eventos_estado: dict, id_: str) -> dict:
    mensaje = next(m for m in eventos_estado["messages"] if m.type == "tool" and m.tool_call_id == id_)
    return json.loads(mensaje.content)


def test_codigo_nunca_visto_se_rechaza(cliente):
    agente = crear_agente(modelo_con(
        llamada("iniciar_configuracion", {}, "i"),
        llamada("agregar_o_reemplazar_componente", {"lugar": "cpu", "codigo": "CPU001"}, "a"),
        texto("No pude agregarlo."),
    ), cliente)
    estado = agente.invoke({"messages": [("user", "Agregá un Intel i5")]}, context=Context(turn=1))
    assert "no salió de ninguna búsqueda" in _resultado_de(estado, "a")["error"]
    assert estado["configuracion"]["componentes"] == {}


def test_codigo_devuelto_por_una_busqueda_se_acepta(cliente):
    agente = crear_agente(modelo_con(
        buscar("cpu"),
        llamada("agregar_o_reemplazar_componente", {"lugar": "cpu", "codigo": "CPU002"}, "a"),
        texto("Listo."),
    ), cliente)
    estado = agente.invoke({"messages": [("user", "Agregá un Ryzen 5")]}, context=Context(turn=1))
    assert estado["configuracion"]["componentes"]["cpu"]["codigo"] == "CPU002"


def test_codigo_escrito_por_el_usuario_se_acepta(cliente):
    agente = crear_agente(modelo_con(
        llamada("agregar_o_reemplazar_componente", {"lugar": "cpu", "codigo": "CPU002"}, "a"),
        texto("Listo."),
    ), cliente)
    estado = agente.invoke({"messages": [("user", "Agregá el CPU002")]}, context=Context(turn=1))
    assert estado["configuracion"]["componentes"]["cpu"]["codigo"] == "CPU002"


def test_codigo_visto_reglas():
    busqueda = AIMessage(content="", tool_calls=[{"name": "buscar_productos", "args": {}, "id": "b"}])
    resultado = ToolMessage('{"productos": [{"codigo": "GPU003"}]}', tool_call_id="b", name="buscar_productos")
    producto = ToolMessage('{"codigo": "GPU009"}', tool_call_id="o", name="obtener_producto")
    mensajes = [HumanMessage("quiero la gpu003 o la GPU004"), busqueda, resultado, producto]
    assert codigo_visto("GPU003", mensajes, None)                       # salió de una búsqueda
    assert codigo_visto("GPU004", mensajes, None)                       # lo escribió el usuario
    assert codigo_visto("gpu003", mensajes, None)                       # sin importar mayúsculas
    assert not codigo_visto("GPU00", mensajes, None)                    # no vale un pedazo de otro código
    # obtener_producto no cuenta: el modelo podría «lavar» un código inventado pidiéndolo primero
    assert not codigo_visto("GPU009", mensajes, None)
    # lo que ya está en el armado cuenta (por ejemplo, tras un clic en «Cambiar» de la interfaz)
    assert codigo_visto("CAB002", [], {"componentes": {"gabinete": {"codigo": "CAB002"}}})
