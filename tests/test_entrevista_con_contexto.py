"""Paso 15: la entrevista usa lo que el usuario ya dijo y, si nombra un juego, busca antes sus requisitos.

Caso que lo motivó: «quiero armar una PC para jugar al Wukong» arrancaba la entrevista desde cero
(«¿para qué la vas a usar?») y nunca buscaba los requisitos del juego.
"""

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import agente as modulo_agente
from agente import AVISO_BUSCAR_REQUISITOS, crear_agente, crear_checkpointer, new_thread, saved_state, stream_turn
from mcp_tienda.armado.entrevista import (completar_con_pistas, con_gama_de_requisitos, nombra_juego_o_programa,
                                          pistas_del_mensaje, respuestas_del_mensaje, siguiente)
from tests.falsos import ModeloFalso, texto
from tools import BASE_DIR, CacheWeb

RESULTADOS_ALTA = [
    {"title": "Requisitos", "url": "https://technical.city/wukong",
     "content": "Recomendados\nProcesador: Intel Core i7-12700\nTarjeta gráfica: NVIDIA RTX 5060\n"}
]


class ModeloQueAnota(ModeloFalso):
    """Modelo falso que guarda los mensajes de cada llamada real al LLM."""
    recibidos: list = []

    def _generate(self, messages, *args, **kwargs):
        self.recibidos.append(list(messages))
        return super()._generate(messages, *args, **kwargs)

    def _stream(self, messages, *args, **kwargs):
        self.recibidos.append(list(messages))
        yield from super()._stream(messages, *args, **kwargs)


class Buscador:
    def invoke(self, _):
        return {"results": RESULTADOS_ALTA}


@pytest.fixture(autouse=True)
def _entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo_agente, "CONV_FILE", tmp_path / "conversaciones.txt")
    monkeypatch.setenv("AMN_TABLA_GAMAS", str(BASE_DIR / "rag" / "docs" / "tabla_cpu_gpu_por_gama.md"))


def _ultima_pregunta(mensajes) -> dict:
    return next(m for m in reversed(mensajes) if isinstance(m, ToolMessage) and m.name == "preguntar_al_usuario").artifact


# --- Funciones de código ----------------------------------------------------------------------

@pytest.mark.parametrize("pedido, esperado", [
    ("Quiero armar una PC para jugar al Wukong", True),
    ("Armame una PC para jugar Fortnite en 1080p", True),
    ("Una PC para AutoCAD y Photoshop", True),
    ("Quiero armar una PC para jugar", False),
    ("PC para jugar online tranqui en 1080p", False),
    ("Necesito una PC para oficina", False),
])
def test_detecta_si_nombra_un_juego_o_programa(pedido, esperado):
    assert nombra_juego_o_programa(pedido) is esperado


def test_lo_que_dice_el_pedido_no_se_vuelve_a_preguntar():
    assert respuestas_del_mensaje("PC para jugar Wukong en 1440p y streamear en Twitch") == {
        "uso": "Jugar", "monitor": "Un monitor 2K (1440p)", "transmitir": "Sí"}
    assert respuestas_del_mensaje("Quiero armar una PC") == {}
    # Dos usos distintos: no se adivina, se pregunta.
    assert respuestas_del_mensaje("PC para jugar y para la facultad") == {}


def test_una_pista_de_mas_adelante_se_aplica_cuando_la_entrevista_llega():
    pistas = pistas_del_mensaje("PC para editar video, con un disco rápido y otro grande")
    respuestas = completar_con_pistas({}, pistas)
    assert respuestas == {"uso": "Diseño o edición de video", "tipo_de_trabajo": "Edición de video"}
    # El usuario contesta la multitarea; la pista del segundo disco entra sola.
    respuestas = completar_con_pistas({**respuestas, "multitarea": "Lo normal"}, pistas)
    assert respuestas["archivos"] == "Sí, muchos"


def test_la_gama_de_los_requisitos_manda_si_es_mas_alta():
    perfil = siguiente({"uso": "Jugar", "monitor": "Un monitor común (1080p)", "transmitir": "No",
                        "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})["perfil"]
    assert perfil["gama"] == "media"
    assert con_gama_de_requisitos(perfil, "alta")["gama"] == "alta"
    assert con_gama_de_requisitos(perfil, "baja")["gama"] == "media"   # nunca baja la gama del uso
    assert con_gama_de_requisitos(perfil, None) is perfil


# --- Agente de punta a punta con modelo falso -------------------------------------------------

def test_wukong_busca_requisitos_antes_y_pregunta_solo_lo_que_falta(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        AIMessage(content="", tool_calls=[
            {"name": "buscar_especificaciones_web", "id": "w1", "args": {"consulta": "Black Myth Wukong"}}]),
        texto("Listo el perfil: arranco el armado."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"),
                          buscador_web=Buscador(), cache_web=CacheWeb(tmp_path / "cache.sqlite"))
    config = new_thread()

    list(stream_turn("Quiero armar una PC para jugar al Wukong en 1080p", config, 1, agente))
    estado = saved_state(config, agente)
    # Una sola llamada al modelo (la búsqueda web); el resto lo hizo el código.
    assert len(modelo.recibidos) == 1 and AVISO_BUSCAR_REQUISITOS in modelo.recibidos[0][-1].text
    assert estado["requisitos"]["gama_sugerida"] == "alta"
    # Uso y pantalla salen del pedido: la primera pregunta es si transmite.
    assert estado["entrevista"]["respuestas"] == {"uso": "Jugar", "monitor": "Un monitor común (1080p)"}
    pregunta = _ultima_pregunta(estado["messages"])
    assert pregunta["pregunta"].startswith("Busqué los requisitos de Black Myth Wukong: piden una PC de gama alta.")
    assert pregunta["opciones"] == ["Sí", "No"]

    for turno, opcion in enumerate(["No", "Lo normal", "No tanto", "No"], start=2):
        list(stream_turn(opcion, config, turno, agente))
    perfil = saved_state(config, agente)["entrevista"]["perfil"]
    # El perfil de 1080p es de gama media, pero los requisitos del juego piden alta: manda alta.
    assert perfil["gama"] == "alta" and perfil["gama_por_requisitos"] is True
    assert len(modelo.recibidos) == 2


def test_sin_juego_nombrado_la_entrevista_arranca_sin_llamar_al_modelo(cliente, tmp_path):
    modelo = ModeloQueAnota(messages=iter([texto("No debería llamarse")]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"))
    config = new_thread()
    list(stream_turn("Quiero armar una PC para jugar en 1440p", config, 1, agente))
    estado = saved_state(config, agente)
    assert modelo.recibidos == []
    assert estado["entrevista"]["respuestas"] == {"uso": "Jugar", "monitor": "Un monitor 2K (1440p)"}
    assert _ultima_pregunta(estado["messages"])["opciones"] == ["Sí", "No"]
