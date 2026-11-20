"""Paso 10: las preguntas de la entrevista se contestan con botones en la app de Streamlit.

El agente pregunta con preguntar_al_usuario (versión 1): sus opciones son botones debajo del turno.
Tocar un botón lo envía como mensaje del usuario (igual que escribirlo) y la entrevista sigue.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import agente
import armado
from mcp_tienda import cliente as modulo_cliente
from tests.falsos import llamada, modelo_con, texto

APP = Path(__file__).parent.parent / "app.py"
SIGUIENTE = "siguiente_pregunta_armado"
USO = ["Oficina o estudio", "Jugar", "Diseño o edición de video", "Programar"]
MULTITAREA = ["Sí, muchos", "Lo normal"]


@pytest.fixture
def app_entrevista(cliente, tmp_path, monkeypatch):
    """La app con un modelo falso que hace la entrevista: pregunta el uso y, al contestar, la multitarea."""
    falso = agente.crear_agente(modelo_con(
        llamada(SIGUIENTE, {}, "e1"),                                        # abre la entrevista por código
        llamada("preguntar_al_usuario", {"pregunta": "¿Para qué la vas a usar principalmente?", "opciones": USO},
                "p1"),                                                       # primer mensaje
        llamada(SIGUIENTE, {"respuesta": "Oficina o estudio"}, "e2"),        # botón «Oficina o estudio»
        llamada("preguntar_al_usuario", {"pregunta": "¿Solés tener muchos programas abiertos a la vez?",
                                         "opciones": MULTITAREA}, "p3"),
        texto("ok")), cliente, agente.crear_checkpointer(tmp_path / "memoria.db"))
    monkeypatch.setattr(agente, "CONV_FILE", tmp_path / "conversaciones.txt")
    monkeypatch.setattr(agente, "get_agent", lambda opcion=agente.OPCION_LOCAL: falso)
    monkeypatch.setattr(modulo_cliente, "get_cliente", lambda: cliente)
    monkeypatch.setattr(armado, "DIR_DATOS", tmp_path)
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    return at


def _botones(at: AppTest) -> list[str]:
    return [b.label for b in at.button if b.key and b.key.startswith("opcion_")]


def test_la_pregunta_de_la_entrevista_muestra_sus_opciones_como_botones(app_entrevista):
    at = app_entrevista
    at.chat_input[0].set_value("Quiero una PC").run()
    assert not at.exception
    assert _botones(at) == USO
    titulos = [s.label for s in at.status]
    assert "🔧 siguiente_pregunta_armado" in titulos
    assert titulos.count("❓ Le hizo una pregunta al usuario") == 1


def test_tocar_un_boton_lo_envia_como_mensaje_y_sigue_la_entrevista(app_entrevista):
    at = app_entrevista
    at.chat_input[0].set_value("Quiero una PC").run()
    next(b for b in at.button if b.label == "Oficina o estudio").click().run()
    assert not at.exception
    assert len(at.session_state.historial) == 2
    assert at.session_state.historial[1][0] == "Oficina o estudio"     # quedó como mensaje del usuario
    assert _botones(at) == MULTITAREA                                  # la pregunta siguiente, con sus botones


def test_los_botones_solo_valen_para_la_ultima_pregunta(app_entrevista):
    at = app_entrevista
    at.chat_input[0].set_value("Quiero una PC").run()
    next(b for b in at.button if b.label == "Oficina o estudio").click().run()
    assert "Jugar" not in _botones(at)
    assert all(b.key.startswith("opcion_1_") for b in at.button if b.key and b.key.startswith("opcion_"))


def test_app_soporta_presupuesto_texto_y_tools_entrevista():
    import app as modulo_app

    assert modulo_app.pesos("2 palos") == "2 palos"
    assert modulo_app.pesos(2_800_000) == "$ 2.800.000"
    assert modulo_app.titulo_llamada({"nombre": "iniciar_configuracion", "args": {"presupuesto": "2 palos"}}) == (
        "🖥️ Inició un armado (presupuesto 2 palos)"
    )
    assert modulo_app.titulo_llamada({"nombre": "buscar_pieza_armado", "args": {"lugar": "ram"}}) == (
        "🔎 Buscó piezas para Memoria RAM"
    )
    assert modulo_app.titulo_llamada({"nombre": "validar_presupuesto", "args": {"texto": "2 palos"}}) == (
        "💰 Validó el presupuesto"
    )
