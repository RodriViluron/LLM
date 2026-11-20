"""Problemas 16, 29 y 32: orden del prompt, ejemplos RAG y consulta previa ante explicaciones."""

import re
from pathlib import Path

import pytest

import agente as modulo_agente
import tools
from agente import (
    PROMPT_SISTEMA,
    crear_agente,
    crear_checkpointer,
    new_thread,
    saved_state,
    stream_turn,
    tema_de_explicacion,
)
from tests.falsos import ModeloFalso, llamada, texto
from tests.test_rag import EmbeddingsDePalabras

RAIZ = Path(__file__).parent.parent


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


@pytest.fixture
def base_minima(tmp_path):
    from rag.ingest import ingestar
    from rag.store import get_store

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guias_de_compra.md").write_text(
        "# Guías de compra\n\n"
        "## UPS: cómo dimensionarla\n"
        "Sumá los watts reales de la PC y monitor y agregá un margen del 20 al 30 %. "
        "Preguntá qué equipos se van a conectar y cuántos minutos tiene que aguantar.\n\n"
        "## Cables: cuál sirve para qué\n"
        "Para conectar la notebook al monitor, preguntá qué puertos tiene cada equipo (HDMI, USB-C o DisplayPort) "
        "y qué largo hace falta.\n",
        encoding="utf-8",
    )
    embeddings = EmbeddingsDePalabras()
    ingestar(docs, embeddings, tmp_path / "chroma_db")
    return get_store(embeddings, tmp_path / "chroma_db")


def test_reglas_del_prompt_numeradas_en_orden_y_entrevista_v1():
    """Problema 16: reglas 1..17 correlativas y regla 17 alineada con la entrevista versión 1."""
    numeros = [int(n) for n in re.findall(r"^(\d+)\.\s", PROMPT_SISTEMA, flags=re.MULTILINE)]
    assert numeros == list(range(1, len(numeros) + 1))
    assert numeros[-1] == 17
    assert "Mostrá cada pregunta con preguntar_al_usuario" in PROMPT_SISTEMA


def test_descripciones_guian_consultas_y_alcance_de_skill(cliente):
    """Problemas 29 y 32: skill aclara que no ensambla; tool RAG incluye las 4 gamas y ejemplos."""
    skill = (RAIZ / "skills" / "armado_pc.md").read_text(encoding="utf-8")
    encabezado = skill.split("---", 2)[1]
    assert "elegir y comprar" in encabezado and "ensamblado" in encabezado

    tool_rag = next(t for t in tools.crear_tools(cliente) if t.name == "consultar_caracteristicas")
    for palabra in ("baja, media, alta, premium", "reparto del presupuesto", "UPS", "cables"):
        assert palabra in tool_rag.description


@pytest.mark.parametrize("pregunta, tema_esperado", [
    ("¿Qué UPS necesito para mi PC?", "ups"),
    ("¿Qué cable uso para conectar la notebook al monitor?", "cables"),
    ("¿Qué es una gama media?", "gamas"),
    ("¿Cómo sé si un procesador es compatible con la motherboard?", "compatibilidad"),
    ("¿Qué importa en una PC para jugar en 1440p?", "actividad"),
])
def test_detecta_preguntas_de_explicacion(pregunta, tema_esperado):
    resultado = tema_de_explicacion(pregunta)
    assert resultado is not None and resultado[0] == tema_esperado


@pytest.mark.parametrize("pedido", [
    "Armame una PC para jugar con $1.200.000",
    "Necesito un cable HDMI de 2 metros",
    "¿Cómo armo una PC paso a paso?",
    "Busco una UPS de 1500 VA",
    "Oficina o estudio",
])
def test_no_confunde_compras_o_ensamblado_con_explicacion(pedido):
    assert tema_de_explicacion(pedido) is None


def test_pregunta_explicacion_sin_rag_pide_consultar_antes_de_responder(cliente, base_minima, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        texto("Decime qué puertos tiene tu notebook."),
        llamada("consultar_caracteristicas", {"query": "cables cuál sirve para conectar notebook al monitor"}),
        texto("Según guias_de_compra.md, decime qué puertos tienen tu notebook y el monitor y qué largo necesitás."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"),
                          base_conocimiento=base_minima)
    config = new_thread()
    list(stream_turn("¿Qué cable uso para conectar la notebook al monitor?", config, 1, agente))

    assert len(modelo.recibidos) == 3
    assert "consultar_caracteristicas" in modelo.recibidos[1][-1].text
    guardados = saved_state(config, agente)["messages"]
    assert [m.type for m in guardados] == ["human", "ai", "tool", "ai"]
    assert "guias_de_compra.md" in guardados[-1].text


def test_pregunta_explicacion_con_preguntar_al_usuario_reintenta_sin_romper_tool_calls(cliente, base_minima, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        llamada("preguntar_al_usuario", {"pregunta": "¿Para qué usás la PC?", "opciones": ["Oficina", "Jugar"]}),
        llamada("consultar_caracteristicas", {"query": "UPS cómo dimensionarla"}),
        texto("Según guias_de_compra.md, contame qué equipos vas a conectar y cuántos minutos querés que aguante."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"),
                          base_conocimiento=base_minima)
    config = new_thread()
    list(stream_turn("¿Qué UPS necesito para mi PC?", config, 1, agente))

    assert len(modelo.recibidos) == 3
    # No dejó el tool_call descartado de preguntar_al_usuario sin ToolMessage en el reintento.
    segundo_llamado = modelo.recibidos[1]
    assert [m.type for m in segundo_llamado] == ["system", "human", "human"]
    assert "consultar_caracteristicas" in segundo_llamado[-1].text
    guardados = saved_state(config, agente)["messages"]
    assert [m.type for m in guardados] == ["human", "ai", "tool", "ai"]


def test_si_ya_consulto_rag_no_reintenta(cliente, base_minima, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        llamada("consultar_caracteristicas", {"query": "UPS cómo dimensionarla"}),
        texto("Según guias_de_compra.md, decime qué equipos conectás."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"),
                          base_conocimiento=base_minima)
    list(stream_turn("¿Qué UPS necesito?", new_thread(), 1, agente))
    assert len(modelo.recibidos) == 2


def test_reintenta_una_sola_vez_si_insiste_sin_rag(cliente, base_minima, tmp_path):
    modelo = ModeloQueAnota(messages=iter([
        texto("Necesitás un cable HDMI."),
        texto("Como te decía, un cable HDMI común."),
    ]))
    agente = crear_agente(modelo, cliente, crear_checkpointer(tmp_path / "memoria.db"),
                          base_conocimiento=base_minima)
    config = new_thread()
    list(stream_turn("¿Qué cable uso para conectar la notebook al monitor?", config, 1, agente))
    assert len(modelo.recibidos) == 2
    assert saved_state(config, agente)["messages"][-1].text == "Como te decía, un cable HDMI común."
