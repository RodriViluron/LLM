"""Paso 12 (#26): entrevista del armado conducida por código, sin gastar llamadas al modelo.

Prueba con modelo falso (`ModeloQueAnota`) todos los caminos de `entrevista_por_codigo`:
- el inicio y las respuestas exactas avanzan sin llamar al modelo;
- los mensajes que no son opción pasan al modelo sin registrar respuesta;
- al completar la entrevista el perfil queda en el estado y el modelo recibe el aviso;
- argumentos inventados en `siguiente_pregunta_armado` no rompen la llamada;
- el presupuesto del primer mensaje (incluso con «1080p» o «4K») se extrae y no se repregunta;
- ante requisitos «sin datos», no se pregunta la gama: sigue la entrevista o se usa el perfil.
"""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import agente as modulo_agente
import mcp_tienda.armado.montos as montos
from agente import PROMPT_SISTEMA, crear_agente, crear_checkpointer, new_thread, pide_armar_pc, saved_state, stream_turn
from mcp_tienda.armado.entrevista import siguiente as siguiente_entrevista
from mcp_tienda.armado.requisitos import leer_requisitos, texto_de_gama, ubicar_requisitos
from tests.falsos import ModeloFalso, llamada, texto
from tools import CacheWeb, Context

RESULTADOS_SIN_DATOS = [
    {"title": "Requisitos", "url": "https://technical.city/f",
     "content": "Recomendados\nProcesador: Intel i5-7300U\nTarjeta gráfica: NVIDIA RTX 3060\n"}
]


class ModeloQueAnota(ModeloFalso):
    """Modelo falso que guarda los mensajes recibidos en cada llamada real al LLM."""
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


def _ultima_pregunta(mensajes) -> dict:
    msg = next(m for m in reversed(mensajes) if isinstance(m, ToolMessage) and m.name == "preguntar_al_usuario")
    return msg.artifact


def test_detector_pide_armar_pc_distingue_pedidos_y_consultas():
    assert pide_armar_pc("Quiero armar una PC")
    assert pide_armar_pc("Armame una PC para jugar Fortnite en 1080p. Tengo 2.800.000 y prefiero Intel.")
    assert pide_armar_pc("Necesito una PC para oficina: planillas y mail. Tengo un millón.")
    assert pide_armar_pc("Quiero una PC para editar video en 4K, con un disco rápido y otro grande. Tengo 5.500.000.")
    assert not pide_armar_pc("¿Cómo armo una PC paso a paso?")
    assert not pide_armar_pc("¿Cuánto cuesta una PC de gama media?")
    assert not pide_armar_pc("¿Qué UPS necesito para mi PC?")
    assert not pide_armar_pc("Busco un procesador Intel")


def test_inicio_y_opcion_avanzan_sin_llamar_al_modelo(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([texto("No debería llamarse")]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()

    list(stream_turn("Quiero armar una PC", config, 1, agente))
    estado_1 = saved_state(config, agente)
    assert estado_1["entrevista"]["pendiente"] == "uso"
    assert _ultima_pregunta(estado_1["messages"])["opciones"] == [
        "Oficina o estudio", "Jugar", "Diseño o edición de video", "Programar"
    ]
    assert modelo.recibidos == []

    list(stream_turn("Oficina o estudio", config, 2, agente))
    estado_2 = saved_state(config, agente)
    assert estado_2["entrevista"]["respuestas"] == {"uso": "Oficina o estudio"}
    assert estado_2["entrevista"]["pendiente"] == "multitarea"
    assert _ultima_pregunta(estado_2["messages"])["opciones"] == ["Sí, muchos", "Lo normal"]
    assert modelo.recibidos == []


def test_texto_que_no_es_opcion_no_se_registra_y_pasa_al_modelo(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        texto("Elegí «Jugar» si querés priorizar placa de video.")
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()

    list(stream_turn("Quiero armar una PC", config, 1, agente))
    assert modelo.recibidos == []

    list(stream_turn("No sé qué elegir, ¿me ayudás?", config, 2, agente))
    estado = saved_state(config, agente)
    assert len(modelo.recibidos) == 1
    assert estado["entrevista"]["pendiente"] == "uso"
    assert estado["entrevista"]["respuestas"] == {}


def test_entrevista_completa_deja_perfil_en_el_estado_y_avisa_al_modelo(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([texto("Listo, te armo una PC de oficina en gama baja.")]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()

    list(stream_turn("Quiero armar una PC", config, 1, agente))
    for turno, opcion in enumerate(["Oficina o estudio", "Lo normal", "No tanto", "No"], start=2):
        list(stream_turn(opcion, config, turno, agente))

    estado = saved_state(config, agente)
    assert estado["entrevista"]["pendiente"] is None
    assert estado["entrevista"]["perfil"]["clave"] == "oficina"
    assert estado["entrevista"]["perfil"]["gama"] == "baja"
    assert len(modelo.recibidos) == 1
    aviso = modelo.recibidos[0][-1].text
    assert "[Aviso del sistema]" in aviso and "oficina" in aviso and "baja" in aviso


def test_argumentos_inventados_en_siguiente_pregunta_no_dan_error(cliente):
    modelo_1 = ModeloQueAnota(messages=iter([
        llamada("siguiente_pregunta_armado", {
            "perfil": "juegos_1080p",
            "completa": False,
            "pregunta": "inventada",
            "opciones": ["A", "B"],
        }, "s1"),
    ]))
    res_1 = crear_agente(modelo_1, cliente).invoke({"messages": [("user", "x")]}, context=Context(turn=1))
    msg_1 = next(m for m in res_1["messages"] if isinstance(m, ToolMessage) and m.name == "siguiente_pregunta_armado")
    assert "error" not in json.loads(msg_1.content)
    assert res_1["entrevista"]["pendiente"] == "uso"

    modelo_2 = ModeloQueAnota(messages=iter([
        llamada("siguiente_pregunta_armado", {
            "respuesta": "Oficina o estudio",
            "perfil": "oficina",
            "completa": True,
            "pregunta": "inventada",
            "opciones": ["C"],
        }, "s2"),
    ]))
    res_2 = crear_agente(modelo_2, cliente).invoke(
        {"messages": [("user", "x")], "entrevista": res_1["entrevista"]}, context=Context(turn=2)
    )
    msg_2 = next(m for m in res_2["messages"] if isinstance(m, ToolMessage) and m.name == "siguiente_pregunta_armado")
    assert "error" not in json.loads(msg_2.content)
    assert res_2["entrevista"]["respuestas"] == {"uso": "Oficina o estudio"}
    assert res_2["entrevista"]["pendiente"] == "multitarea"


def test_extraer_presupuesto_de_frases_con_resoluciones():
    assert montos.extraer_presupuesto_mensaje(
        "Armame una PC para jugar Fortnite en 1080p. Tengo 2.800.000 y prefiero Intel."
    )["monto"] == 2_800_000
    assert montos.extraer_presupuesto_mensaje(
        "Necesito una PC para oficina: planillas y mail. Tengo un millón."
    )["monto"] == 1_000_000
    assert montos.extraer_presupuesto_mensaje(
        "Quiero una PC para editar video en 4K, con un disco rápido y otro grande. Tengo 5.500.000."
    )["monto"] == 5_500_000
    assert montos.extraer_presupuesto_mensaje("Armame una PC para jugar GTA 5") is None
    ambiguo = montos.extraer_presupuesto_mensaje("Quiero una PC entre 1 y 2 millones")
    assert ambiguo["monto"] is None and ambiguo["ambiguo"] is True


def test_monto_del_primer_mensaje_se_guarda_y_no_se_vuelve_a_preguntar(cliente, tmp_path):
    # Simula un modelo que igual intenta repreguntar el presupuesto tras finalizar la entrevista: el middleware lo frena.
    modelo = ModeloQueAnota(messages=iter([
        llamada("preguntar_al_usuario", {
            "pregunta": "¿Cuál es tu presupuesto?",
            "opciones": ["Gama baja (cerca de $ 1.000.000)", "Otro monto"],
        }, "p_dup"),
        llamada("iniciar_configuracion", {"presupuesto": 1_000_000, "perfil_uso": "Oficina o estudio"}, "i1"),
        texto("Inicié tu armado de oficina con $ 1.000.000."),
        texto("Inicié tu armado de oficina con $ 1.000.000."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()

    list(stream_turn("Necesito una PC para oficina: planillas y mail. Tengo un millón.", config, 1, agente))
    assert saved_state(config, agente)["entrevista"]["presupuesto"] == 1_000_000

    # «para oficina» ya contesta el uso (paso 15): la entrevista arranca en la multitarea.
    assert saved_state(config, agente)["entrevista"]["respuestas"] == {"uso": "Oficina o estudio"}
    for turno, opcion in enumerate(["Lo normal", "No tanto", "No"], start=2):
        list(stream_turn(opcion, config, turno, agente))

    estado = saved_state(config, agente)
    assert estado["configuracion"]["presupuesto"] == 1_000_000
    assert len(modelo.recibidos) == 4
    assert "NO preguntes el presupuesto" in modelo.recibidos[0][-1].text
    assert not any(m.type == "tool" and m.name == "preguntar_al_usuario"
                   and "presupuesto" in m.text.lower() for m in estado["messages"])


def test_monto_ambiguo_en_primer_mensaje_se_pregunta_despues(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        llamada("preguntar_al_usuario", {
            "pregunta": "¿Qué presupuesto preferís: $ 1.000.000 o $ 2.000.000?",
            "opciones": ["$ 1.000.000", "$ 2.000.000"],
        }, "p1"),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()

    list(stream_turn("Quiero armar una PC entre 1 y 2 millones", config, 1, agente))
    for turno, opcion in enumerate(["Oficina o estudio", "Lo normal", "No tanto", "No"], start=2):
        list(stream_turn(opcion, config, turno, agente))

    estado = saved_state(config, agente)
    assert estado["entrevista"]["presupuesto"] is None
    assert "Todavía no hay presupuesto confirmado" in modelo.recibidos[0][-1].text
    assert "más de un monto" in modelo.recibidos[0][-1].text
    assert _ultima_pregunta(estado["messages"])["opciones"] == ["$ 1.000.000", "$ 2.000.000"]


def test_requisitos_sin_datos_no_preguntan_la_gama(tmp_path, monkeypatch, cliente):
    tabla_vacia = tmp_path / "tabla.md"
    tabla_vacia.write_text("| componente | modelo | gama | puntaje |\n|---|---|---|---|\n", encoding="utf-8")
    monkeypatch.setenv("AMN_TABLA_GAMAS", str(tabla_vacia))

    assert "NO preguntes la gama" in PROMPT_SISTEMA
    ubicados = ubicar_requisitos(leer_requisitos(RESULTADOS_SIN_DATOS), tabla_vacia)
    assert "no preguntes la gama" in texto_de_gama(ubicados).lower()

    class Buscador:
        def invoke(self, _):
            return {"results": RESULTADOS_SIN_DATOS}

    # Caso 1: sin entrevista previa, buscar_especificaciones_web da sin datos y el modelo intenta preguntar la gama.
    # El código evita preguntar la gama y redirige a la entrevista.
    opciones_gama = ["Gama baja (cerca de $ 1.000.000)", "Gama media (cerca de $ 2.800.000)"]
    agente_1 = crear_agente(
        ModeloQueAnota(messages=iter([
            AIMessage(content="", tool_calls=[
                {"name": "buscar_especificaciones_web", "id": "w1", "args": {"consulta": "requisitos Fortnite"}}
            ]),
            llamada("preguntar_al_usuario", {"pregunta": "¿Qué gama querés?", "opciones": opciones_gama}, "p1"),
        ])),
        cliente, buscador_web=Buscador(), cache_web=CacheWeb(tmp_path / "cache1.sqlite"),
    )
    estado_1 = agente_1.invoke({"messages": [("user", "una compu para Fortnite")]}, context=Context(turn=1))
    pregunta_1 = _ultima_pregunta(estado_1["messages"])
    assert "gama" not in pregunta_1["pregunta"].lower()
    assert pregunta_1["opciones"] == ["Oficina o estudio", "Jugar", "Diseño o edición de video", "Programar"]
    assert estado_1["entrevista"]["pendiente"] == "uso"

    # Caso 2: con perfil completo, el modelo busca Fortnite (sin datos) e intenta preguntar la gama.
    # El middleware lo frena y exige usar la gama del perfil.
    perfil = siguiente_entrevista({
        "uso": "Jugar", "monitor": "Un monitor común (1080p)", "transmitir": "No",
        "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No",
    })["perfil"]
    modelo_2 = ModeloQueAnota(messages=iter([
        AIMessage(content="", tool_calls=[
            {"name": "buscar_especificaciones_web", "id": "w2", "args": {"consulta": "requisitos Fortnite"}}
        ]),
        llamada("preguntar_al_usuario", {"pregunta": "¿Qué gama querés?", "opciones": opciones_gama}, "p2"),
        llamada("iniciar_configuracion", {"presupuesto": 2_800_000, "perfil_uso": perfil["nombre"]}, "i2"),
        texto("Armado iniciado en gama media."),
        texto("Armado iniciado en gama media."),
    ]))
    agente_2 = crear_agente(modelo_2, cliente, buscador_web=Buscador(), cache_web=CacheWeb(tmp_path / "cache2.sqlite"))
    estado_2 = agente_2.invoke({
        "messages": [("user", "seguimos")],
        "entrevista": {"respuestas": {}, "pendiente": None, "perfil": perfil, "presupuesto": 2_800_000},
    }, context=Context(turn=1))
    assert estado_2["configuracion"]["presupuesto"] == 2_800_000
    assert "gama media" in modelo_2.recibidos[2][-1].text
    assert not any(m.type == "tool" and m.name == "preguntar_al_usuario" for m in estado_2["messages"])


OPCIONES_PRESUPUESTO = ["Gama baja (cerca de $ 1.000.000)", "Gama media (cerca de $ 2.800.000)",
                        "Gama alta (cerca de $ 5.300.000)", "Gama premium (cerca de $ 8.800.000)", "Otro monto"]


def test_con_perfil_y_sin_datos_la_pregunta_del_presupuesto_no_se_pisa():
    """Con el perfil completo, las opciones de gama son la pregunta del presupuesto (regla 15)."""
    from tools import aviso_sin_datos

    perfil = siguiente_entrevista({"uso": "Oficina o estudio", "multitarea": "Lo normal",
                                   "archivos": "No tanto", "mejora": "No"})["perfil"]
    requisitos = {"gama_sugerida": None, "sin_datos": ["RTX 9999"]}
    pregunta, opciones, nueva = aviso_sin_datos("¿Cuál es tu presupuesto?", OPCIONES_PRESUPUESTO, requisitos,
                                                {"respuestas": {}, "pendiente": None, "perfil": perfil})
    assert (pregunta, opciones, nueva) == ("¿Cuál es tu presupuesto?", OPCIONES_PRESUPUESTO, None)


def test_preguntar_el_presupuesto_con_gamas_no_es_repregunta_si_falta_el_monto():
    from agente import _es_pregunta_redundante

    mensaje = AIMessage(content="", tool_calls=[{"name": "preguntar_al_usuario", "id": "p1",
                                                 "args": {"pregunta": "¿Qué gama y presupuesto?",
                                                          "opciones": OPCIONES_PRESUPUESTO}}])
    assert _es_pregunta_redundante(mensaje, False, ya_tiene_presupuesto=False) == (False, False)
    assert _es_pregunta_redundante(mensaje, False, ya_tiene_presupuesto=True) == (False, True)
