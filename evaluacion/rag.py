"""Evaluación del RAG (consultar_caracteristicas), problemas 5, 29 y 30.

Corre las consultas de evaluacion/conjuntos/rag_consultas.yaml contra la base real (rag/chroma_db,
embeddings locales) y mide, sobre los 4 primeros fragmentos que recibe el modelo:
- acierto@1: el primero es el correcto (es del archivo esperado y contiene el texto `debe`, o uno de ellos).
- acierto@4: alguno de los 4 es el correcto.
- mezcla: cuántos de los 4 hablan de otra gama (los que confunden al modelo).
- tiempo_promedio_s: tiempo promedio por consulta en segundos.

Uso:  uv run python -m evaluacion.rag [--solo-vectores | --hyde]
      --solo-vectores mide la búsqueda por parecido sola, sin filtro de gama ni búsqueda exacta.
      --hyde pide al modelo local una respuesta hipotética corta para buscar con ella (sin mostrarla ni citarla).
"""

import argparse
import json
import re
import time

import yaml

from agente import separar_razonamiento
from mcp_tienda.armado.gamas import GAMAS
from mcp_tienda.config import RAIZ
from model import get_model
from rag.consulta import buscar_en_documentacion
from rag.store import get_store

CONJUNTO = RAIZ / "evaluacion" / "conjuntos" / "rag_consultas.yaml"
K = 4

PROMPT_HYDE = (
    "Escribí en español una respuesta hipotética breve (2 o 3 frases) como si fuera un párrafo "
    "de la guía de compra o especificaciones de una tienda de computación en Argentina. "
    "Sin títulos, sin listas ni viñetas, y sin hacer preguntas al usuario.\n\n"
    "Pregunta: {consulta}"
)


def gamas_de(texto: str) -> set[str]:
    """Gamas de las que habla un fragmento: «gama X» o una fila de la tabla «| X |»."""
    t = texto.lower()
    return {g for g in GAMAS if re.search(rf"gama {g}\b|\| {g} \|", t)}


def _texto_de_respuesta(respuesta) -> str:
    """Extrae texto plano de la respuesta del modelo y descarta <think> si apareció."""
    crudo = respuesta.text if hasattr(respuesta, "text") else str(getattr(respuesta, "content", respuesta))
    return separar_razonamiento(crudo)[1].strip()


def generar_hipotetico(modelo, consulta: str) -> str:
    """Respuesta hipotética corta en español para buscar en el RAG (nunca se muestra ni se cita)."""
    texto = _texto_de_respuesta(modelo.invoke(PROMPT_HYDE.format(consulta=consulta)))
    return texto or consulta


def evaluar(solo_vectores: bool = False, hyde: bool = False, modelo=None, store=None,
            consultas: list[dict] | None = None) -> dict:
    if solo_vectores and hyde:
        raise ValueError("Usá solo una variante por vez: --solo-vectores o --hyde.")
    consultas = consultas if consultas is not None else yaml.safe_load(CONJUNTO.read_text(encoding="utf-8"))["consultas"]
    store = store or get_store()
    if hyde and modelo is None:
        modelo = get_model()
    modo = "solo_vectores" if solo_vectores else ("hyde" if hyde else "actual")
    filas = []
    for c in consultas:
        inicio = time.perf_counter()
        if solo_vectores:
            fragmentos = [{"fuente": d.metadata["source"], "texto": d.page_content}
                          for d in store.similarity_search(c["consulta"], k=K)]
        elif hyde:
            # El texto hipotético solo se usa para buscar; nunca se guarda, muestra ni cita.
            hipotetico = generar_hipotetico(modelo, c["consulta"])
            fragmentos = buscar_en_documentacion(store, c["consulta"], k=K, texto_busqueda=hipotetico)[:K]
        else:
            fragmentos = buscar_en_documentacion(store, c["consulta"], k=K)[:K]
        tiempo_s = round(time.perf_counter() - inicio, 4)
        debe = c["debe"] if isinstance(c["debe"], list) else [c["debe"]]   # vale cualquiera de las alternativas
        bien = [f["fuente"] == c["fuente"] and any(d in f["texto"] for d in debe) for f in fragmentos]
        filas.append({**c, "acierto1": bool(bien and bien[0]), "acierto4": any(bien),
                      "otra_gama": (sum(bool(gamas_de(f["texto"]) - {c["gama"]}) for f in fragmentos)
                                    if c["gama"] else 0),
                      "primero": fragmentos[0]["fuente"] if fragmentos else None,
                      "tiempo_s": tiempo_s})
    n = len(filas)
    tiempo_total = round(sum(f["tiempo_s"] for f in filas), 4)
    return {
        "modo": modo,
        "consultas": n,
        "acierto1": sum(f["acierto1"] for f in filas) / n,
        "acierto4": sum(f["acierto4"] for f in filas) / n,
        "mezcla": sum(f["otra_gama"] for f in filas) / (K * n),
        "tiempo_total_s": tiempo_total,
        "tiempo_promedio_s": round(tiempo_total / n, 4),
        "detalle": filas,
    }


def _archivo_salida(modo: str):
    nombres = {"solo_vectores": "rag_solo_vectores.json", "hyde": "rag_hyde.json", "actual": "rag.json"}
    return RAIZ / "evaluacion" / "resultados" / nombres[modo]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--solo-vectores", action="store_true")
    grupo.add_argument("--hyde", action="store_true")
    args = parser.parse_args()
    r = evaluar(solo_vectores=args.solo_vectores, hyde=args.hyde)
    for f in r["detalle"]:
        marca = "✓" if f["acierto1"] else ("~" if f["acierto4"] else "✗")
        print(f"{marca} [{f['gama'] or '-':7}] {f['consulta'][:60]:60} primero={f['primero']}  "
              f"otra gama: {f['otra_gama']}  ({f['tiempo_s']:.2f}s)")
    print(f"\nacierto@1 {r['acierto1']:.0%}   acierto@4 {r['acierto4']:.0%}   "
          f"fragmentos con otra gama {r['mezcla']:.0%}   "
          f"tiempo promedio {r['tiempo_promedio_s']:.2f}s/consulta   ({r['consultas']} consultas)")
    salida = _archivo_salida(r["modo"])
    salida.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Detalle en {salida}")


if __name__ == "__main__":
    main()
