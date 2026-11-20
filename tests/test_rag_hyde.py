"""Problema 30: experimento HyDE en evaluacion/rag.py (con modelo y embeddings falsos)."""

import pytest
from langchain_core.documents import Document

from evaluacion.rag import _archivo_salida, evaluar, generar_hipotetico
from rag.ingest import ingestar
from rag.store import get_store
from tests.falsos import EmbeddingsDePalabras, texto


class _StoreEspia:
    """Store mínimo que registra exactamente qué texto recibe similarity_search."""

    def __init__(self, resultados: list[Document]):
        self.llamadas: list[tuple[str, dict | None]] = []
        self.resultados = resultados

    def similarity_search(self, query: str, k: int = 4, filter: dict | None = None):
        self.llamadas.append((query, filter))
        return self.resultados[:k]


class _ModeloEspia:
    def __init__(self, respuestas: list[str]):
        self.prompts: list[str] = []
        self._respuestas = iter(respuestas)

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return texto(next(self._respuestas))


CONSULTA = [{"consulta": "qué procesador lleva una PC de gama media",
             "fuente": "gamas.md", "debe": "Procesador: Intel i5", "gama": "media"}]


def test_hyde_busca_con_el_texto_generado_sin_razonamiento():
    store = _StoreEspia([
        Document(page_content="Gama media: Procesador: Intel i5 o Ryzen 5.", metadata={"source": "gamas.md", "gama": "media"})
    ])
    modelo = _ModeloEspia([
        "<think>Thinking in English first...</think>"
        "Una computadora de gama media utiliza procesadores Intel i5 o Ryzen 5 equilibrados."
    ])
    resultado = evaluar(hyde=True, modelo=modelo, store=store, consultas=CONSULTA)

    assert len(modelo.prompts) == 1 and CONSULTA[0]["consulta"] in modelo.prompts[0]
    buscado, filtro = store.llamadas[0]
    assert buscado == "Una computadora de gama media utiliza procesadores Intel i5 o Ryzen 5 equilibrados."
    assert buscado != CONSULTA[0]["consulta"]
    assert "<think>" not in buscado and "Thinking" not in buscado
    assert filtro == {"gama": "media"}
    # El texto hipotético solo se usa para buscar: no se guarda ni se cita en el detalle.
    assert "hipotetico" not in resultado["detalle"][0]
    assert "equilibrados" not in str(resultado["detalle"][0])
    assert resultado["modo"] == "hyde" and resultado["acierto1"] == 1.0


def test_hyde_mantiene_filtro_de_gama_y_tabla_exacta_de_la_consulta_original(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gamas.md").write_text(
        "# Gamas\n\n## Gama media\n\n"
        "Procesador Intel i5 o Ryzen 5 con 16 GB de RAM y placa de video de entrada para jugar en 1080p.\n"
        "Incluye fuente estándar y almacenamiento SSD NVMe de 512 GB a 1 TB para programas diarios y juegos.\n\n"
        "## Gama alta\n\n"
        "Procesador Intel i7 o Ryzen 7 con 32 GB de RAM, refrigeración dedicada y SSD M.2 NVMe de 1 a 2 TB.\n"
        "Pensada para resolución 1440p, edición de video exigente y almacenamiento secundario de gran capacidad.\n",
        encoding="utf-8",
    )
    (docs / "tabla_cpu_gpu_por_gama.md").write_text(
        "# Tabla de referencia\n\n## Cómo leer esta tabla\n\n"
        "Cada fila indica la gama oficial de un procesador o placa de video según los criterios del equipo.\n"
        "Si un modelo no aparece en la tabla, el asistente responde sin datos y no la adivina nunca.\n\n"
        "## Placas de video\n\n### Placas de video de gama alta\n\n"
        "| componente | modelo | gama |\n|---|---|---|\n| gpu | RTX 5060 | alta |\n",
        encoding="utf-8",
    )
    ingestar(docs, EmbeddingsDePalabras(), tmp_path / "db")
    store = get_store(EmbeddingsDePalabras(), tmp_path / "db")

    # Aunque la respuesta hipotética nombre otra gama o un modelo inventado, mandan la consulta original y su tabla.
    modelo = _ModeloEspia([
        "En gama media solemos ver discos básicos, aunque la GTX 9999 ya no figura en catálogo.",
    ])
    consultas = [{"consulta": "qué disco va en gama alta para RTX 5060",
                  "fuente": "tabla_cpu_gpu_por_gama.md", "debe": "| gpu | RTX 5060 | alta |", "gama": "alta"}]
    r = evaluar(hyde=True, modelo=modelo, store=store, consultas=consultas)
    assert r["acierto1"] == 1.0 and r["acierto4"] == 1.0

    # También sin modelo nombrado: la consulta pide gama alta, así que el filtro no trae fragmentos de gama media
    # aunque el documento hipotético la mencione.
    consultas_gama = [{"consulta": "qué disco usa la gama alta",
                       "fuente": "gamas.md", "debe": "SSD M.2 NVMe de 1 a 2 TB", "gama": "alta"}]
    r_gama = evaluar(
        hyde=True,
        modelo=_ModeloEspia(["En gama media con disco SSD NVMe y refrigeración dedicada para almacenamiento secundario."]),
        store=store,
        consultas=consultas_gama,
    )
    assert r_gama["acierto1"] == 1.0 and r_gama["detalle"][0]["otra_gama"] == 0


def test_sin_hyde_no_invoca_modelo_y_busca_con_consulta():
    store = _StoreEspia([
        Document(page_content="Procesador: Intel i5", metadata={"source": "gamas.md", "gama": "media"})
    ])
    modelo = _ModeloEspia(["no debería llamarse"])
    r = evaluar(hyde=False, modelo=modelo, store=store, consultas=CONSULTA)
    assert modelo.prompts == []
    assert store.llamadas[0][0] == CONSULTA[0]["consulta"]
    assert r["modo"] == "actual" and r["tiempo_promedio_s"] >= 0


def test_hipotetico_vacio_cae_a_consulta_original():
    modelo = _ModeloEspia(["<think>razonamiento cortado sin cierre"])
    assert generar_hipotetico(modelo, "qué cooler lleva la gama baja") == "qué cooler lleva la gama baja"


def test_archivos_de_salida_y_variantes_excluyentes():
    assert _archivo_salida("solo_vectores").name == "rag_solo_vectores.json"
    assert _archivo_salida("actual").name == "rag.json"
    assert _archivo_salida("hyde").name == "rag_hyde.json"
    with pytest.raises(ValueError, match="una variante"):
        evaluar(solo_vectores=True, hyde=True, store=_StoreEspia([]), consultas=CONSULTA)
