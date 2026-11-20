"""Paso 7: interfaz en Streamlit (chat + panel «Armá tu PC»).

Se prueba con el probador de Streamlit (AppTest), que ejecuta app.py sin navegador, con un modelo
falso y el servidor MCP real. Los clics en «Cambiar» y «Confirmar pedido» no pasan por el modelo.
"""

import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import agente
import armado
from mcp_tienda import cliente as modulo_cliente
from tests.falsos import buscar, llamada, modelo_con, texto

ARMADO = {"cpu": "CPU002", "motherboard": "MOT003", "ram": "RAM003", "gpu": "GPU003",
          "almacenamiento": "ALM003", "fuente": "FUE006", "gabinete": "GAB004"}
PEDIDO = "Armame una PC para jugar con $1.200.000"
APP = Path(__file__).parent.parent / "app.py"


def _guion_de_armado():
    pasos = [llamada("iniciar_configuracion", {"presupuesto": 1_200_000, "perfil_uso": "juegos 1080p"}, "i")]
    for n, (lugar, codigo) in enumerate(ARMADO.items()):   # busca y después agrega cada pieza
        pasos += [buscar(lugar),
                  llamada("agregar_o_reemplazar_componente", {"lugar": lugar, "codigo": codigo}, f"a{n}")]
    return [*pasos, texto("Listo: te armé una PC para jugar en 1080p.")]


@pytest.fixture
def app(cliente, tmp_path, monkeypatch):
    """La app con un agente de modelo falso, memoria temporal y el servidor MCP de los tests."""
    agente_falso = agente.crear_agente(modelo_con(*_guion_de_armado()), cliente,
                                       agente.crear_checkpointer(tmp_path / "memoria.db"))
    monkeypatch.setattr(agente, "CONV_FILE", tmp_path / "conversaciones.txt")
    monkeypatch.setattr(agente, "get_agent", lambda opcion=agente.OPCION_LOCAL: agente_falso)
    monkeypatch.setattr(modulo_cliente, "get_cliente", lambda: cliente)
    monkeypatch.setattr(armado, "DIR_DATOS", tmp_path)   # los pedidos de prueba van a una base temporal
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    return at


def _configuracion(at: AppTest) -> dict:
    return agente.saved_state(at.session_state.config)["configuracion"]


def _boton(at: AppTest, etiqueta: str):
    return next(b for b in at.button if b.label == etiqueta)


def _armar(at: AppTest) -> AppTest:
    at.chat_input[0].set_value(PEDIDO).run()
    assert not at.exception
    return at


def _cambiar_por_la_primera_alternativa(at: AppTest, lugar: str) -> str:
    at.button(key=f"cambiar_{lugar}").click().run()
    elegir = next(b for b in at.button if b.key and b.key.startswith("elegir_"))
    codigo = elegir.key.removeprefix("elegir_")
    elegir.click().run()
    assert not at.exception
    return codigo


def test_el_selector_de_modelo_muestra_las_opciones_configuradas(app):
    selector = app.selectbox(key="modelo")
    assert selector.options == list(agente.opciones_de_modelo().values())
    assert selector.value == agente.OPCION_LOCAL   # por defecto, el modelo local


def test_sin_armado_el_panel_invita_a_pedirlo(app):
    assert any("Todavía no hay un armado" in i.value for i in app.info)
    assert not [b for b in app.button if b.label == "✅ Confirmar pedido"]


def test_el_chat_muestra_las_tools_y_el_panel_las_tarjetas(app, catalogo):
    at = _armar(app)
    # Chat: la pregunta, una línea por tool (como en el ejemplo de la cátedra) y la respuesta.
    assert at.chat_message[0].markdown[0].value == PEDIDO
    titulos = [s.label for s in at.status]
    assert titulos[0].startswith("🖥️ Inició un armado") and "➕ Placa de video: GPU003" in titulos
    assert any("Listo: te armé una PC" in m.value for m in at.markdown)
    # Panel: una tarjeta por pieza, con código, nombre, precio y stock, y su botón Cambiar.
    assert {b.key for b in at.button if b.key and b.key.startswith("cambiar_")} == {f"cambiar_{s}" for s in ARMADO}
    textos = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    for codigo in ARMADO.values():
        producto = catalogo.obtener(codigo)
        assert codigo in textos and producto.nombre in textos
    # Total y presupuesto: salen del estado, que calculó la tienda.
    total = sum(catalogo.obtener(c).precio for c in ARMADO.values())
    assert [m.value for m in at.metric] == [f"$ {total:,.0f}".replace(",", "."), "$ 1.200.000"]
    assert any("✅ Compatible" in m.value for m in at.markdown)


def test_el_historial_y_el_panel_se_reconstruyen_al_reabrir(app):
    _armar(app)
    otra_sesion = AppTest.from_file(str(APP), default_timeout=60).run()   # como abrir la app de nuevo
    assert otra_sesion.chat_message[0].markdown[0].value == PEDIDO
    assert len([b for b in otra_sesion.button if b.key and b.key.startswith("cambiar_")]) == len(ARMADO)


def test_cambiar_reemplaza_solo_esa_pieza_sin_pasar_por_el_modelo(app):
    at = _armar(app)
    antes = _configuracion(at)
    mensajes_antes = len(agente.saved_state(at.session_state.config)["messages"])

    nuevo = _cambiar_por_la_primera_alternativa(at, "gpu")

    despues = _configuracion(at)
    assert despues["componentes"]["gpu"]["codigo"] == nuevo != "GPU003"
    for lugar in set(ARMADO) - {"gpu"}:
        assert despues["componentes"][lugar]["codigo"] == antes["componentes"][lugar]["codigo"]
    assert despues["reporte"]["estado_general"] != "incompatible"     # la alternativa era compatible
    diferencia = despues["componentes"]["gpu"]["precio"] - antes["componentes"]["gpu"]["precio"]
    assert despues["total"] == antes["total"] + diferencia
    # El modelo no intervino: no hay mensajes nuevos en la conversación.
    assert len(agente.saved_state(at.session_state.config)["messages"]) == mensajes_antes
    assert any("cambiada por" in s.value for s in at.success)
    assert at.metric[0].value == f"$ {despues['total']:,.0f}".replace(",", ".")


def test_cancelar_el_cambio_no_toca_nada(app):
    at = _armar(app)
    antes = _configuracion(at)
    at.button(key="cambiar_fuente").click().run()
    at.button(key="cancelar_cambio").click().run()
    assert _configuracion(at) == antes
    assert not [b for b in at.button if b.key and b.key.startswith("elegir_")]


def test_no_se_puede_confirmar_con_piezas_sin_stock(app):
    at = _armar(app)
    sin_stock = [s for s, p in _configuracion(at)["componentes"].items() if p["stock"] == 0]
    assert sin_stock, "el armado de prueba incluye piezas sin stock"
    assert _boton(at, "✅ Confirmar pedido").disabled
    assert any("Sin stock" in c.value for c in at.caption)


def test_confirmar_pedido_lo_hace_el_usuario_con_un_clic(app, tmp_path):
    at = _armar(app)
    for lugar in [s for s, p in _configuracion(at)["componentes"].items() if p["stock"] == 0]:
        _cambiar_por_la_primera_alternativa(at, lugar)        # el usuario reemplaza lo que no tiene stock
    config = _configuracion(at)
    assert not _boton(at, "✅ Confirmar pedido").disabled

    _boton(at, "✅ Confirmar pedido").click().run()

    assert any("Pedido P-00001 confirmado" in s.value for s in at.success)
    pedidos = armado.PedidosLocales(tmp_path / "pedidos.sqlite").listar()
    assert len(pedidos) == 1 and pedidos[0]["total"] == config["total"]
    assert pedidos[0]["codigos"] == {s: p["codigo"] for s, p in config["componentes"].items()}


def test_si_el_precio_cambio_no_confirma_y_muestra_el_total_nuevo(app, catalogo, tmp_path):
    at = _armar(app)
    for lugar in [s for s, p in _configuracion(at)["componentes"].items() if p["stock"] == 0]:
        _cambiar_por_la_primera_alternativa(at, lugar)
    total_visto = _configuracion(at)["total"]

    # Entre que el usuario mira el total y hace clic, la tienda sube el precio del procesador.
    with sqlite3.connect(catalogo.ruta_db) as conn:
        conn.execute("UPDATE productos SET precio = precio + 5000 WHERE codigo = 'CPU002'")
    try:
        _boton(at, "✅ Confirmar pedido").click().run()
        assert any("No se confirmó el pedido" in e.value and "El total cambió" in e.value for e in at.error)
        assert armado.PedidosLocales(tmp_path / "pedidos.sqlite").listar() == []
        assert _configuracion(at)["total"] == total_visto + 5000      # el panel ya muestra el precio nuevo
        # Ahora que vio el total nuevo, confirma de nuevo y sale.
        _boton(at, "✅ Confirmar pedido").click().run()
        assert any("confirmado" in s.value for s in at.success)
    finally:
        with sqlite3.connect(catalogo.ruta_db) as conn:
            conn.execute("UPDATE productos SET precio = precio - 5000 WHERE codigo = 'CPU002'")


def test_confirmar_no_es_una_tool(cliente):
    from tools import crear_tools

    assert not [t.name for t in crear_tools(cliente) if "confirm" in t.name.lower()]
