"""Problema 5: el RAG devolvía fragmentos de la gama equivocada.

A. La ingesta corta por sección (encabezados de Markdown) y cada fragmento lleva «documento › sección»
   y, en la metadata, la gama de su sección.
C. Si la consulta nombra una gama, el código busca solo en los fragmentos de esa gama (y los generales).
D. Si la consulta nombra un CPU o una GPU, el código responde primero con su fila de la tabla.
"""

import pytest

from rag.consulta import buscar_en_documentacion, gama_de_la_consulta
from rag.ingest import ingestar
from rag.store import get_store
from tests.falsos import EmbeddingsDePalabras

GAMAS = """# Gamas de PC

> **Fecha:** 2026-11-10

## Qué es una gama

La gama agrupa componentes según rendimiento y precio. Hay cuatro: baja, media, alta y premium.

## Gama media

Procesador: Intel i5 o Ryzen 5. RAM: 16 GB. Disco: de 512 GB a 1 TB.

## Gama alta

Procesador: Intel i7 o Ryzen 7. RAM: 32 GB. Disco: SSD M.2 NVMe de 1 a 2 TB.
"""

TABLA = """# Tabla de referencia de CPU y GPU por gama

## Cómo leer esta tabla

Cada fila dice en qué gama está un modelo de placa de video. Un modelo que no está en la tabla no tiene
gama: el asistente lo dice y no la adivina. La tabla sale de los criterios de gamas.md.

## Placas de video (GPU)

### Placas de video de gama media

| componente | modelo | gama | puntaje |
|---|---|---|---|
| gpu | RTX 5050 | media | |

### Placas de video de gama alta

| componente | modelo | gama | puntaje |
|---|---|---|---|
| gpu | RTX 5060 | alta | |
"""


@pytest.fixture
def base(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gamas.md").write_text(GAMAS, encoding="utf-8")
    (docs / "tabla_cpu_gpu_por_gama.md").write_text(TABLA, encoding="utf-8")
    embeddings = EmbeddingsDePalabras()
    ingestar(docs, embeddings, tmp_path / "db")
    return get_store(embeddings, tmp_path / "db"), docs / "tabla_cpu_gpu_por_gama.md"


def test_cada_fragmento_es_una_seccion_con_su_titulo_y_su_gama(base):
    store, _ = base
    indexado = store.get()
    pares = zip(indexado["documents"], indexado["metadatas"], strict=True)
    por_seccion = {m["seccion"]: (d, m["gama"]) for d, m in pares}
    texto, gama = por_seccion["Gamas de PC › Gama alta"]
    assert gama == "alta"
    assert texto.startswith("Gamas de PC › Gama alta\n")                  # el título va dentro del fragmento
    assert "Gama media" not in texto and "16 GB" not in texto             # no se mezcla con la sección anterior
    assert por_seccion["Gamas de PC › Qué es una gama"][1] == "general"   # nombra varias gamas: general
    tabla = por_seccion["Tabla de referencia de CPU y GPU por gama › Placas de video (GPU) › "
                        "Placas de video de gama alta"]
    assert tabla[1] == "alta" and "| gpu | RTX 5060 | alta |" in tabla[0] and "RTX 5050" not in tabla[0]


@pytest.mark.parametrize("consulta, gama", [
    ("qué disco usa la gama alta", "alta"), ("cuánta memoria lleva una PC premium", "premium"),
    ("la Gama Baja lleva placa de video?", "baja"), ("cómo armo una PC", None),
    ("diferencia entre gama media y gama alta", None),   # nombra dos: no se filtra
])
def test_gama_de_la_consulta(consulta, gama):
    assert gama_de_la_consulta(consulta) == gama


def test_el_filtro_por_gama_no_trae_otras_gamas(base):
    store, tabla = base
    fragmentos = buscar_en_documentacion(store, "qué disco y cuánta RAM usa la gama alta", ruta_tabla=tabla)
    assert fragmentos[0]["texto"].startswith("Gamas de PC › Gama alta")
    assert all("Gama media" not in f["texto"] for f in fragmentos)
    assert {f["gama"] for f in fragmentos} <= {"alta", "general"}


def test_sin_gama_en_la_consulta_busca_en_todo(base):
    store, tabla = base
    fragmentos = buscar_en_documentacion(store, "procesador RAM disco", ruta_tabla=tabla)
    assert {f["gama"] for f in fragmentos} >= {"media", "alta"}


def test_un_modelo_concreto_se_responde_con_la_tabla(base):
    store, tabla = base
    primero = buscar_en_documentacion(store, "en qué gama está la RTX 5060", ruta_tabla=tabla)[0]
    assert primero["exacta"] and primero["fuente"] == "tabla_cpu_gpu_por_gama.md"
    assert "| gpu | RTX 5060 | alta |" in primero["texto"]
    falta = buscar_en_documentacion(store, "y la GTX 1060?", ruta_tabla=tabla)[0]
    assert falta["exacta"] and "| gpu | GTX 1060 | sin datos |" in falta["texto"]


def test_una_base_vieja_sin_metadata_de_gama_sigue_respondiendo(tmp_path):
    """Si no se reindexó, el filtro no encuentra nada y se busca sin filtro."""
    from langchain_core.documents import Document

    store = get_store(EmbeddingsDePalabras(), tmp_path / "db")
    store.add_documents([Document("Gama alta: disco SSD M.2 NVMe de 1 a 2 TB", metadata={"source": "gamas.md"})])
    assert buscar_en_documentacion(store, "qué disco usa la gama alta", ruta_tabla=tmp_path / "no.md")


def test_desempate_por_intencion_entre_gamas_y_reparto(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gamas.md").write_text(
        "# Gamas\n\n## Gama media\n\n"
        "Disco de 512 GB a 1 TB NVMe y procesador Intel i5 con 16 GB de RAM para jugar 1080p sin problemas.\n"
        "Pensado para armados equilibrados con placa dedicada de entrada y fuente acorde.\n\n"
        "## Gama premium\n\n"
        "Valor: más de $ 5.780.000 con procesador Intel Ultra 9, 64 GB DDR5 y SSD NVMe de 2 TB para 4K.\n"
        "Incluye almacenamiento secundario SATA y refrigeración dedicada de gama superior.\n",
        encoding="utf-8",
    )
    (docs / "reparto_presupuesto.md").write_text(
        "# Reparto del presupuesto\n\n## Reparto del presupuesto en gama media\n\n"
        "Una PC de gama media cuesta $ 2.762.000. Gama media disco principal disco secundario SSD NVMe disco 21 %.\n"
        "Disco almacenamiento disco secundario HDD o SSD SATA para juegos pesados en gama media.\n\n"
        "## Reparto del presupuesto en gama premium\n\n"
        "Una PC de gama premium en la tienda cuesta típicamente $ 9.324.000 según precios actuales.\n"
        "Porcentaje por componente en gama premium: procesador 15 %, memoria 30 %, placa de video 23 %.\n",
        encoding="utf-8",
    )
    embeddings = EmbeddingsDePalabras()
    ingestar(docs, embeddings, tmp_path / "db")
    store = get_store(embeddings, tmp_path / "db")
    tabla_vacia = tmp_path / "sin_tabla.md"

    componentes = buscar_en_documentacion(store, "qué disco lleva una PC de gama media", ruta_tabla=tabla_vacia)
    assert componentes[0]["fuente"] == "gamas.md"

    costo = buscar_en_documentacion(store, "cuánto cuesta una PC de gama premium", ruta_tabla=tabla_vacia)
    assert costo[0]["fuente"] == "reparto_presupuesto.md"
