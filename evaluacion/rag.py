"""Evaluación del RAG (consultar_caracteristicas), problema 5.

Corre las consultas de evaluacion/conjuntos/rag_consultas.yaml contra la base real (rag/chroma_db,
embeddings locales) con la misma búsqueda que usa la tool (rag.consulta.buscar_en_documentacion) y mide,
sobre los 4 primeros fragmentos que recibe el modelo:
- acierto@1: el primero es el correcto (es del archivo esperado y contiene el texto `debe`, o uno de ellos).
- acierto@4: alguno de los 4 es el correcto.
- mezcla: cuántos de los 4 hablan de otra gama (los que confunden al modelo).

Uso:  uv run python -m evaluacion.rag [--solo-vectores]
      --solo-vectores mide la búsqueda por parecido sola, sin filtro de gama ni búsqueda exacta.
"""

import argparse
import json
import re

import yaml

from mcp_tienda.armado.gamas import GAMAS
from mcp_tienda.config import RAIZ
from rag.consulta import buscar_en_documentacion
from rag.store import get_store

CONJUNTO = RAIZ / "evaluacion" / "conjuntos" / "rag_consultas.yaml"
K = 4


def gamas_de(texto: str) -> set[str]:
    """Gamas de las que habla un fragmento: «gama X» o una fila de la tabla «| X |»."""
    t = texto.lower()
    return {g for g in GAMAS if re.search(rf"gama {g}\b|\| {g} \|", t)}


def evaluar(solo_vectores: bool = False) -> dict:
    consultas = yaml.safe_load(CONJUNTO.read_text(encoding="utf-8"))["consultas"]
    store = get_store()
    filas = []
    for c in consultas:
        if solo_vectores:
            fragmentos = [{"fuente": d.metadata["source"], "texto": d.page_content}
                          for d in store.similarity_search(c["consulta"], k=K)]
        else:
            fragmentos = buscar_en_documentacion(store, c["consulta"], k=K)[:K]
        debe = c["debe"] if isinstance(c["debe"], list) else [c["debe"]]   # vale cualquiera de las alternativas
        bien = [f["fuente"] == c["fuente"] and any(d in f["texto"] for d in debe) for f in fragmentos]
        filas.append({**c, "acierto1": bool(bien and bien[0]), "acierto4": any(bien),
                      "otra_gama": (sum(bool(gamas_de(f["texto"]) - {c["gama"]}) for f in fragmentos)
                                    if c["gama"] else 0),
                      "primero": fragmentos[0]["fuente"] if fragmentos else None})
    n = len(filas)
    return {"consultas": n, "acierto1": sum(f["acierto1"] for f in filas) / n,
            "acierto4": sum(f["acierto4"] for f in filas) / n,
            "mezcla": sum(f["otra_gama"] for f in filas) / (K * n), "detalle": filas}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--solo-vectores", action="store_true")
    args = parser.parse_args()
    r = evaluar(args.solo_vectores)
    for f in r["detalle"]:
        marca = "✓" if f["acierto1"] else ("~" if f["acierto4"] else "✗")
        print(f"{marca} [{f['gama'] or '-':7}] {f['consulta'][:60]:60} primero={f['primero']}  "
              f"otra gama: {f['otra_gama']}")
    print(f"\nacierto@1 {r['acierto1']:.0%}   acierto@4 {r['acierto4']:.0%}   "
          f"fragmentos con otra gama {r['mezcla']:.0%}   ({r['consultas']} consultas)")
    nombre = "rag_solo_vectores.json" if args.solo_vectores else "rag.json"
    salida = RAIZ / "evaluacion" / "resultados" / nombre
    salida.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Detalle en {salida}")


if __name__ == "__main__":
    main()
