"""Las tools de la entrevista del armado en el agente (paso 10, versión 1).

La entrevista la pregunta el agente con preguntar_al_usuario, usando las opciones que devuelve
siguiente_pregunta_armado (JSON). Con modelo falso y servidor MCP real se prueba cada paso: las
preguntas, las respuestas que no son opción, el perfil y la búsqueda de piezas con el perfil.
"""

import json

from langchain_core.messages import ToolMessage

from agente import crear_agente
from mcp_tienda.armado.entrevista import siguiente
from tests.falsos import llamada, modelo_con, texto

SIGUIENTE = "siguiente_pregunta_armado"
OFICINA_COMPLETA = ["Oficina o estudio", "Lo normal", "No tanto", "No"]


def _mensajes(resultado: dict, nombre: str) -> list[ToolMessage]:
    return [m for m in resultado["messages"] if isinstance(m, ToolMessage) and m.name == nombre]


def _json_de(resultado: dict, nombre: str, indice: int = 0) -> dict:
    return json.loads(_mensajes(resultado, nombre)[indice].content)


def _turno(cliente, pasos: list, estado: dict | None = None) -> dict:
    """Un turno del agente con modelo falso; `estado` es la entrevista que ya guardó un turno anterior."""
    agente = crear_agente(modelo_con(*pasos, texto("ok")), cliente)
    entrada = {"messages": [("user", "x")]}
    if estado is not None:
        entrada["entrevista"] = estado
    return agente.invoke(entrada)


def test_la_primera_pregunta_es_el_uso_con_sus_opciones(cliente):
    resultado = _turno(cliente, [llamada(SIGUIENTE, {}, "e1")])
    datos = _json_de(resultado, SIGUIENTE)
    assert datos["completa"] is False and datos["pregunta"]["id"] == "uso"
    assert datos["pregunta"]["opciones"] == ["Oficina o estudio", "Jugar", "Diseño o edición de video", "Programar"]
    assert resultado["entrevista"]["pendiente"] == "uso"


def test_una_respuesta_valida_pasa_a_la_siguiente_pregunta(cliente):
    resultado = _turno(cliente, [llamada(SIGUIENTE, {"respuesta": "Oficina o estudio"}, "e2")],
                       estado={"respuestas": {}, "pendiente": "uso", "perfil": None})
    assert _json_de(resultado, SIGUIENTE)["pregunta"]["id"] == "multitarea"
    assert resultado["entrevista"]["respuestas"] == {"uso": "Oficina o estudio"}
    assert resultado["entrevista"]["pendiente"] == "multitarea"


def test_una_respuesta_que_no_es_opcion_devuelve_error_y_no_cambia_el_estado(cliente):
    resultado = _turno(cliente, [llamada(SIGUIENTE, {"respuesta": "Jugar a Fortnite"}, "e2")],
                       estado={"respuestas": {}, "pendiente": "uso", "perfil": None})
    error = _json_de(resultado, SIGUIENTE)
    assert "Oficina o estudio" in error["error"] and "Jugar" in error["error"]
    assert resultado["entrevista"]["respuestas"] == {} and resultado["entrevista"]["pendiente"] == "uso"


def test_la_entrevista_completa_da_el_perfil_en_el_estado(cliente):
    estado = {"respuestas": {}, "pendiente": "uso", "perfil": None}
    for respuesta in OFICINA_COMPLETA:
        resultado = _turno(cliente, [llamada(SIGUIENTE, {"respuesta": respuesta}, "e")], estado=estado)
        estado = resultado["entrevista"]
    final = _json_de(resultado, SIGUIENTE)
    assert final["completa"] is True and final["perfil"]["clave"] == "oficina"
    assert estado["perfil"]["gama"] == "baja" and estado["pendiente"] is None


def test_dos_llamadas_a_la_entrevista_en_el_mismo_paso_no_rompen_el_turno(cliente):
    """Pasó con el modelo local: pidió la siguiente pregunta dos veces en un mismo mensaje."""
    from langchain_core.messages import AIMessage
    doble = AIMessage(content="", tool_calls=[
        {"name": SIGUIENTE, "args": {}, "id": "d1"},
        {"name": SIGUIENTE, "args": {"respuesta": "Oficina o estudio"}, "id": "d2"}])
    agente = crear_agente(modelo_con(doble, texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "PC para oficina")]})
    assert resultado["entrevista"]["pendiente"] == "uso"


def test_buscar_pieza_aplica_la_gama_del_perfil(cliente):
    perfil = siguiente({"uso": "Oficina o estudio", "multitarea": "Lo normal", "archivos": "No tanto",
                        "mejora": "No"})["perfil"]
    agente = crear_agente(modelo_con(
        llamada("buscar_pieza_armado", {"lugar": "cpu", "limite": 20}, "b1"), texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "PC para oficina")],
                               "entrevista": {"respuestas": {}, "pendiente": None,
                                              "perfil": perfil, "presupuesto": 1_000_000}})
    busqueda = _json_de(resultado, "buscar_pieza_armado")
    assert busqueda["productos"], "debería haber procesadores de gama baja en el catálogo de prueba"
    assert all(p["gama"] == "baja" for p in busqueda["productos"])


def test_buscar_ram_para_64_gb_sugiere_la_cantidad(cliente):
    perfil = siguiente({"uso": "Jugar", "monitor": "Un televisor o monitor 4K", "multitarea": "Lo normal",
                        "archivos": "No tanto", "mejora": "No"})["perfil"]
    agente = crear_agente(modelo_con(
        llamada("buscar_pieza_armado", {"lugar": "ram", "limite": 20}, "b1"), texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "PC para jugar en 4K")],
                               "entrevista": {"respuestas": {}, "pendiente": None,
                                              "perfil": perfil, "presupuesto": 9_000_000}})
    busqueda = _json_de(resultado, "buscar_pieza_armado")
    assert busqueda["productos"], "con 64 GB en 2 unidades tiene que haber memorias en el catálogo de prueba"
    for p in busqueda["productos"]:
        assert p["atributos"]["capacidad_gb"] >= 32
        assert p["atributos"]["capacidad_gb"] * p["cantidad_sugerida"] >= 64


def test_un_codigo_de_buscar_pieza_armado_se_puede_agregar(cliente):
    # Antes buscar_pieza_armado no contaba para el control de códigos inventados (problema 20) y
    # agregar_o_reemplazar_componente rechazaba la pieza que acababa de encontrar.
    perfil = siguiente({"uso": "Oficina o estudio", "multitarea": "Lo normal", "archivos": "No tanto",
                        "mejora": "No"})["perfil"]
    estado_inicial = {"entrevista": {"respuestas": {}, "pendiente": None, "perfil": perfil, "presupuesto": 1_000_000}}
    busqueda = crear_agente(modelo_con(llamada("buscar_pieza_armado", {"lugar": "cpu"}, "b1"), texto("ok")),
                            cliente).invoke({"messages": [("user", "PC para oficina")], **estado_inicial})
    codigo = _json_de(busqueda, "buscar_pieza_armado")["productos"][0]["codigo"]
    agente = crear_agente(modelo_con(
        llamada("buscar_pieza_armado", {"lugar": "cpu"}, "b1"),
        llamada("agregar_o_reemplazar_componente", {"lugar": "cpu", "codigo": codigo}, "a1"),
        texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "PC para oficina")], **estado_inicial})
    assert resultado["configuracion"]["componentes"]["cpu"]["codigo"] == codigo


def test_buscar_pieza_sin_entrevista_avisa(cliente):
    agente = crear_agente(modelo_con(llamada("buscar_pieza_armado", {"lugar": "cpu"}, "b1"), texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "buscá un procesador")]})
    assert "entrevista" in _json_de(resultado, "buscar_pieza_armado")["error"]


def test_monto_del_usuario_se_valida_por_codigo(cliente):
    agente = crear_agente(modelo_con(
        llamada("validar_presupuesto", {"texto": "20 lucas"}, "v1"),
        llamada("validar_presupuesto", {"texto": "2 palos"}, "v2"),
        texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "tengo 20 lucas")]})
    chico = json.loads(_mensajes(resultado, "validar_presupuesto")[0].content)
    assert chico["alcanza"] is False and chico["minimo"] == 919_000
    dos_palos = json.loads(_mensajes(resultado, "validar_presupuesto")[1].content)
    assert dos_palos["alcanza"] is True and dos_palos["gama"] == "baja"


def test_monto_ambiguo_pide_aclaracion(cliente):
    agente = crear_agente(modelo_con(llamada("validar_presupuesto", {"texto": "20"}, "v1"), texto("ok")), cliente)
    resultado = agente.invoke({"messages": [("user", "tengo 20")]})
    assert json.loads(_mensajes(resultado, "validar_presupuesto")[0].content)["ambiguo"] is True


def test_todas_las_opciones_son_texto_y_los_ids_son_unicos():
    """YAML lee «No» sin comillas como False: una opción así no se puede elegir."""
    from mcp_tienda.armado.perfiles import cargar_entrevista
    preguntas = cargar_entrevista()["preguntas"]
    assert len({p["id"] for p in preguntas}) == len(preguntas)
    for pregunta in preguntas:
        assert all(isinstance(opcion, str) for opcion in pregunta["opciones"]), pregunta["id"]
