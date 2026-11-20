"""Evaluación de la extracción de atributos.

Compara lo que extraen las regex contra las etiquetas. Por cada atributo informa:
- exactitud: correctos / productos con el dato conocido
- erróneos: valores extraídos que NO coinciden con la etiqueta (incluye inventar un dato desconocido).
  Es la métrica que más importa: un erróneo puede terminar en un armado incompatible.
- faltantes: el dato se conocía pero no se pudo extraer (la regla dirá «sin datos»).

Hoy las etiquetas salen del generador del catálogo de prueba. OJO: como las regex se escribieron
conociendo el generador, el número da optimista. La medición que vale es sobre la muestra de
50 productos reales etiquetados a mano (cuando llegue el catálogo de la tienda).

Uso:  python -m evaluacion.extraccion [--detalle]
"""

import argparse
import json
from collections import defaultdict

from mcp_tienda.config import DIR_CATALOGO_PRUEBA, RAIZ
from mcp_tienda.esquemas import normalizar_categoria
from mcp_tienda.ingesta.extraccion import extraer_atributos


def _iguales(extraido, esperado) -> bool:
    if isinstance(esperado, list) or isinstance(extraido, list):
        return set(extraido or []) == set(esperado or [])
    if isinstance(esperado, float) or isinstance(extraido, float):
        return extraido is not None and esperado is not None and abs(extraido - esperado) < 0.01
    return extraido == esperado


def evaluar(productos: list[dict], etiquetas: dict) -> dict:
    por_atributo = defaultdict(lambda: {"con_dato": 0, "correctos": 0, "erroneos": 0, "faltantes": 0})
    errores = []
    categorias_ok = 0
    for p in productos:
        etiqueta = etiquetas[p["codigo"]]
        categoria = normalizar_categoria(p["categoria"])
        categorias_ok += categoria == etiqueta["categoria"]
        extraidos = extraer_atributos(etiqueta["categoria"], p["nombre"], p["descripcion"])
        for atributo, esperado in etiqueta["atributos"].items():
            clave = f"{etiqueta['categoria']}.{atributo}"
            extraido = extraidos.get(atributo)
            m = por_atributo[clave]
            if esperado is not None:
                m["con_dato"] += 1
            if extraido is None:
                if esperado is not None:
                    m["faltantes"] += 1
            elif _iguales(extraido, esperado):
                m["correctos"] += 1
            else:
                m["erroneos"] += 1
                errores.append({"codigo": p["codigo"], "atributo": clave,
                                "esperado": esperado, "extraido": extraido})
    total = {k: sum(m[k] for m in por_atributo.values())
             for k in ("con_dato", "correctos", "erroneos", "faltantes")}
    return {
        "productos": len(productos),
        "exactitud_categoria": categorias_ok / len(productos),
        "por_atributo": dict(por_atributo),
        "total": total,
        "exactitud_total": total["correctos"] / total["con_dato"],
        "errores": errores,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--detalle", action="store_true", help="muestra cada valor erróneo")
    args = parser.parse_args()

    productos = json.loads((DIR_CATALOGO_PRUEBA / "productos_crudos.json").read_text(encoding="utf-8"))
    etiquetas = json.loads((DIR_CATALOGO_PRUEBA / "etiquetas.json").read_text(encoding="utf-8"))
    r = evaluar(productos, etiquetas)

    print(f"Productos: {r['productos']}   Categoría bien normalizada: {r['exactitud_categoria']:.1%}\n")
    print(f"{'atributo':34} {'con dato':>8} {'exactitud':>10} {'erróneos':>9} {'faltantes':>10}")
    for clave, m in sorted(r["por_atributo"].items()):
        exactitud = m["correctos"] / m["con_dato"] if m["con_dato"] else float("nan")
        print(f"{clave:34} {m['con_dato']:>8} {exactitud:>10.1%} {m['erroneos']:>9} {m['faltantes']:>10}")
    t = r["total"]
    print(f"\n{'TOTAL':34} {t['con_dato']:>8} {r['exactitud_total']:>10.1%} {t['erroneos']:>9} {t['faltantes']:>10}")
    print("\nOJO: etiquetas del generador; el número real sale de la muestra de productos reales.")

    if args.detalle and r["errores"]:
        print("\nErróneos:")
        for e in r["errores"]:
            print(f"  {e['codigo']} {e['atributo']}: esperado={e['esperado']!r} extraído={e['extraido']!r}")

    salida = RAIZ / "evaluacion" / "resultados"
    salida.mkdir(exist_ok=True)
    (salida / "extraccion.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
