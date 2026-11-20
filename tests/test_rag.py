"""Paso 5: RAG con el patrón de la cátedra (rag/store.py, rag/ingest.py, consultar_caracteristicas).

Se prueba con documentos de prueba y embeddings falsos; la prueba con embeddings reales está
marcada y se saltea si no hay un servidor local con el modelo de embeddings.
"""

import json
import os
import urllib.request

import pytest

import tools
from agente import crear_agente, eventos
from rag.ingest import cargar_documentos, ingestar
from rag.store import DOCS_DIR, get_store
from tests.falsos import EmbeddingsDePalabras, llamada, modelo_con, texto

GAMAS = """# Gamas de PC

> **Título:** Gamas de PC
> **Fecha:** 2026-11-10
> **Fuente:** documento de prueba

<!-- Este comentario es una indicación para quien escribe: NO se indexa. -->

## Gama media

Una PC de gama media usa un procesador de seis núcleos y una placa de video dedicada de ocho gigas.
Alcanza para jugar en resolución 1080p con calidad alta y para trabajar con diseño gráfico liviano.

## Gama alta

Una PC de gama alta usa procesadores de ocho o más núcleos y placas de video de dieciséis gigas.
Alcanza para jugar en 4K, editar video pesado y hacer streaming al mismo tiempo sin problemas.
"""

UPS = """# Guías de compra

> **Título:** Guías de compra
> **Fecha:** 2026-11-10
> **Fuente:** documento de prueba

## Cómo dimensionar una UPS

Para dimensionar una UPS se suma el consumo en watts de la computadora y del monitor y se agrega
un margen de seguridad. La potencia en VA no es lo mismo que la potencia en watts: hay que mirar
los watts reales. La autonomía indica cuántos minutos aguanta el equipo durante un corte de luz.
"""

VACIO = """# Tutorial de armado

> **Título:** Tutorial de armado

## Paso 1

<!-- Escribir acá: cómo se coloca el procesador. -->
"""


@pytest.fixture
def base(tmp_path):
    """Documentos de prueba ya indexados en una base Chroma temporal."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gamas.md").write_text(GAMAS, encoding="utf-8")
    (docs / "guias_de_compra.md").write_text(UPS, encoding="utf-8")
    (docs / "tutorial_armado_pc.md").write_text(VACIO, encoding="utf-8")
    embeddings = EmbeddingsDePalabras()
    resumen = ingestar(docs, embeddings, tmp_path / "chroma_db")
    return get_store(embeddings, tmp_path / "chroma_db"), resumen


def test_ingesta_indexa_lo_escrito_y_saltea_lo_vacio(base):
    store, resumen = base
    assert resumen["documentos"] == 2 and resumen["chunks"] >= 2
    assert resumen["vacios"] == ["tutorial_armado_pc.md"]
    indexado = store.get()
    assert {m["source"] for m in indexado["metadatas"]} == {"gamas.md", "guias_de_compra.md"}
    assert not any("NO se indexa" in d for d in indexado["documents"])   # los comentarios quedan afuera


def test_reingestar_no_duplica(base, tmp_path):
    store, resumen = base
    ingestar(tmp_path / "docs", EmbeddingsDePalabras(), tmp_path / "chroma_db")
    assert len(get_store(EmbeddingsDePalabras(), tmp_path / "chroma_db").get()["ids"]) == resumen["chunks"]


def test_ingesta_sin_ningun_documento_escrito_avisa(tmp_path):
    (tmp_path / "tutorial.md").write_text(VACIO, encoding="utf-8")
    with pytest.raises(SystemExit, match="Ningún documento tiene contenido"):
        ingestar(tmp_path, EmbeddingsDePalabras(), tmp_path / "db")


def test_consultar_caracteristicas_cita_el_archivo_de_origen(base, cliente):
    store, _ = base
    modelo = modelo_con(llamada("consultar_caracteristicas", {"query": "cómo dimensionar una UPS en watts"}),
                        texto("Según guias_de_compra.md, hay que mirar los watts reales."))
    estado = crear_agente(modelo, cliente, base_conocimiento=store).invoke(
        {"messages": [("user", "¿Cómo elijo una UPS?")]}, context=tools.Context(turn=3))

    resultado = next(e for e in eventos(estado["messages"]) if e["tipo"] == "resultado")
    # El modelo recibe los fragmentos numerados con su archivo.
    assert resultado["texto"].startswith("[1] Fuente: guias_de_compra.md")
    assert "watts reales" in resultado["texto"]
    # La interfaz recibe un reporte corto por artifact.
    assert resultado["datos"][0]["archivo"] == "guias_de_compra.md"
    # Las fuentes quedan en el estado con su turno, como en el ejemplo de la cátedra.
    assert {"turn": 3, "title": "Documentación: guias_de_compra.md", "url": "rag/docs/guias_de_compra.md"} \
        in estado["sources"]


def test_recupera_el_fragmento_correcto(base):
    store, _ = base
    mejor = store.similarity_search("qué placa de video y procesador tiene la gama media para jugar 1080p", k=1)[0]
    assert mejor.metadata["source"] == "gamas.md" and "gama media" in mejor.page_content.lower()


def test_sin_base_vectorial_la_tool_lo_dice_en_vez_de_romper(cliente, tmp_path, monkeypatch):
    import rag.store

    monkeypatch.setattr(rag.store, "DB_DIR", tmp_path / "no_existe")
    tools._base_conocimiento.cache_clear()
    modelo = modelo_con(llamada("consultar_caracteristicas", {"query": "gama media"}), texto("No pude consultar."))
    estado = crear_agente(modelo, cliente).invoke({"messages": [("user", "x")]}, context=tools.Context(turn=1))
    mensaje = next(m for m in estado["messages"] if m.type == "tool")
    assert "python -m rag.ingest" in mensaje.content
    tools._base_conocimiento.cache_clear()


def test_los_documentos_existen_con_encabezado():
    # Los que escribe el grupo, más el reparto del presupuesto (evaluacion/reparto_presupuesto.py) y la tabla de
    # gamas (mcp_tienda/armado/tabla_gamas.py), que se generan. No hay tutorial de ensamblado: la tienda entrega
    # la PC armada.
    esperados = {"gamas.md", "caracteristicas_por_actividad.md", "tabla_cpu_gpu_por_gama.md",
                 "guia_compatibilidad.md", "guias_de_compra.md", "reparto_presupuesto.md"}
    assert {p.name for p in DOCS_DIR.glob("*.md")} == esperados
    for ruta in DOCS_DIR.glob("*.md"):
        contenido = ruta.read_text(encoding="utf-8")
        assert contenido.startswith("# ")
        for campo in ("**Título:**", "**Fecha:**", "**Fuente:**"):
            assert campo in contenido, f"{ruta.name} no tiene {campo}"
    # La tabla de gamas trae los títulos de las columnas que lee el código.
    tabla = (DOCS_DIR / "tabla_cpu_gpu_por_gama.md").read_text(encoding="utf-8")
    assert "| componente | modelo | gama | puntaje |" in tabla


def test_el_prompt_pide_citar_la_documentacion():
    from agente import construir_prompt

    assert "consultar_caracteristicas" in construir_prompt()


def _embeddings_locales_disponibles() -> bool:
    if os.getenv("MODEL_PROVIDER", "ollama") != "ollama":
        return False
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    modelo = os.getenv("EMBEDDINGS_MODEL", "bge-m3")
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=2) as respuesta:
            return any(m["name"].startswith(modelo) for m in json.load(respuesta)["models"])
    except OSError:
        return False


@pytest.mark.embeddings
@pytest.mark.skipif(not _embeddings_locales_disponibles(), reason="No hay Ollama con el modelo de embeddings")
def test_embeddings_reales_recuperan_por_significado(tmp_path):
    """Con embeddings de verdad, una consulta sin palabras en común encuentra el documento correcto."""
    from model import get_embeddings

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gamas.md").write_text(GAMAS, encoding="utf-8")
    (docs / "guias_de_compra.md").write_text(UPS, encoding="utf-8")
    ingestar(docs, get_embeddings(), tmp_path / "db")
    store = get_store(get_embeddings(), tmp_path / "db")
    mejor = store.similarity_search("se me apaga la compu cuando se corta la luz", k=1)[0]
    assert mejor.metadata["source"] == "guias_de_compra.md"


def test_cargar_documentos_reales_no_rompe():
    """Cada documento real está escrito o figura como vacío (y no se indexa). Son 6: no hay tutorial."""
    documentos, vacios = cargar_documentos()
    assert len(documentos) + len(vacios) == 6
