"""Reporte de calidad del catálogo real: qué datos del armado de PC se pueden leer y cuáles no.

Pasa cada producto por el lector del formato de la tienda (mcp_tienda/ingesta/formato_amn.py) e informa:

- cobertura: por cada atributo, en cuántas piezas se pudo leer (lo que no se lee queda «sin datos»);
- avisos: los productos que no siguen la convención de carga, uno por renglón, con el motivo:
    ilegible       el dato no está donde va (falta «SOCKET:», falta «[12va]»...)
    contradiccion  el nombre y la descripción dicen cosas distintas
    sin_evidencia  no hay ningún indicio del dato
    formato_prg    acá se lee bien, pero el sistema actual (3PC.PRG) lo lee mal

El CSV de avisos es la lista para corregir en el catálogo de la tienda. Corregido el catálogo, se
vuelve a correr y el número baja: es la métrica de este paso.

No necesita iniciar sesión (no mira precios). Uso:
    uv run python -m evaluacion.calidad_catalogo                         lee la API (AMN_API_URL)
    uv run python -m evaluacion.calidad_catalogo --guardar bajada.json   además guarda lo que bajó
    uv run python -m evaluacion.calidad_catalogo --archivo bajada.json   lee una bajada guardada
"""

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from mcp_tienda.config import RAIZ
from mcp_tienda.esquemas import cargar_esquemas
from mcp_tienda.ingesta import formato_amn
from mcp_tienda.ingesta.fuentes.api import FuenteAPI

URL_POR_DEFECTO = "https://api.amn.com.ar/api"
DIR_RESULTADOS = RAIZ / "evaluacion" / "resultados"


def recortar(item: dict) -> dict:
    """Se queda solo con lo que usa el lector (deja afuera costos, márgenes y etiquetas internas)."""
    p = item["product"]
    categoria = p.get("category") or {}
    return {
        "product": {
            "sku": p["sku"], "name": p["name"], "desc": p.get("desc") or "", "hdesc": p.get("hdesc") or "",
            "category": {"code": categoria.get("code"), "name": categoria.get("name")},
            "brand": {"name": (p.get("brand") or {}).get("name")},
        },
        "inventory": {"totalQty": (item.get("inventory") or {}).get("totalQty")},
    }


def analizar(items: Iterable[dict]) -> dict:
    """Devuelve la cobertura por atributo y la lista de avisos. `items` tiene la forma de la API."""
    esquemas = cargar_esquemas()
    por_categoria: dict = defaultdict(lambda: {"piezas": 0, "en_el_armado": 0, "fuera_del_armado": 0,
                                               "con_avisos": 0, "con_dato": Counter()})
    avisos: list[dict] = []
    leidos = 0
    for item in items:
        leidos += 1
        p = item["product"]
        lectura = formato_amn.leer(p.get("name") or "", p.get("desc"), p.get("hdesc"),
                                   (p.get("category") or {}).get("code"))
        if lectura.categoria is None:
            continue
        c = por_categoria[lectura.categoria]
        c["piezas"] += 1
        if lectura.fuera_del_armado:
            c["fuera_del_armado"] += 1
            continue
        c["en_el_armado"] += 1
        c["con_avisos"] += bool(lectura.avisos)
        for atributo, valor in lectura.atributos.items():
            c["con_dato"][atributo] += valor is not None
        for aviso in lectura.avisos:
            avisos.append({"sku": p["sku"], "nombre": p["name"], "categoria": lectura.categoria,
                           "atributo": aviso.atributo, "clase": aviso.clase, "detalle": aviso.detalle})

    resumen = {}
    for categoria, c in sorted(por_categoria.items()):
        total = c["en_el_armado"]
        resumen[categoria] = {
            "piezas": c["piezas"], "en_el_armado": total, "fuera_del_armado": c["fuera_del_armado"],
            "con_avisos": c["con_avisos"],
            "cobertura": {a: {"con_dato": c["con_dato"][a], "total": total}
                          for a in esquemas[categoria].atributos},
        }
    return {
        "productos_leidos": leidos,
        "piezas_de_pc": sum(c["piezas"] for c in resumen.values()),
        "por_categoria": resumen,
        "avisos_por_clase": dict(Counter(a["clase"] for a in avisos)),
        "avisos": avisos,
    }


def imprimir(r: dict) -> None:
    print(f"Productos leídos: {r['productos_leidos']}   Piezas de PC: {r['piezas_de_pc']}\n")
    print(f"{'categoría':16} {'piezas':>7} {'en armado':>10} {'fuera':>6} {'con avisos':>11}")
    for categoria, c in r["por_categoria"].items():
        print(f"{categoria:16} {c['piezas']:>7} {c['en_el_armado']:>10} {c['fuera_del_armado']:>6} "
              f"{c['con_avisos']:>11}")
    print("\nCobertura por atributo (piezas en el armado con el dato leído):")
    for categoria, c in r["por_categoria"].items():
        for atributo, m in c["cobertura"].items():
            porcentaje = m["con_dato"] / m["total"] if m["total"] else 0.0
            print(f"  {categoria + '.' + atributo:42} {m['con_dato']:>4}/{m['total']:<4} {porcentaje:>6.0%}")
    print("\nAvisos por clase:", r["avisos_por_clase"] or "ninguno")


def guardar(r: dict, carpeta: Path = DIR_RESULTADOS) -> tuple[Path, Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_json = carpeta / "calidad_catalogo.json"
    ruta_json.write_text(json.dumps({k: v for k, v in r.items() if k != "avisos"}, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    ruta_csv = carpeta / "calidad_catalogo_avisos.csv"
    with ruta_csv.open("w", encoding="utf-8-sig", newline="") as archivo:   # utf-8-sig: abre bien en Excel
        escritor = csv.DictWriter(archivo, fieldnames=["categoria", "sku", "nombre", "atributo", "clase", "detalle"],
                                  delimiter=";")
        escritor.writeheader()
        escritor.writerows(sorted(r["avisos"], key=lambda a: (a["categoria"], a["clase"], a["sku"])))
    return ruta_json, ruta_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archivo", type=Path, help="bajada guardada con --guardar (no consulta la API)")
    parser.add_argument("--guardar", type=Path, help="guarda lo bajado de la API, recortado. No subirlo al repo.")
    parser.add_argument("--detalle", action="store_true", help="muestra cada aviso en pantalla")
    args = parser.parse_args()

    if args.archivo:
        items = json.loads(args.archivo.read_text(encoding="utf-8"))
    else:
        fuente = FuenteAPI(os.getenv("AMN_API_URL") or URL_POR_DEFECTO)
        items = [recortar(item) for item in fuente.iterar_items()]
        if args.guardar:
            args.guardar.parent.mkdir(parents=True, exist_ok=True)
            args.guardar.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

    r = analizar(items)
    imprimir(r)
    if args.detalle:
        print()
        for a in sorted(r["avisos"], key=lambda a: (a["categoria"], a["clase"], a["sku"])):
            print(f"  [{a['clase']:13}] {a['categoria']:14} {a['sku']:8} {a['atributo']:24} {a['detalle']}")
    ruta_json, ruta_csv = guardar(r)
    print(f"\nResumen: {ruta_json}\nAvisos para corregir: {ruta_csv}")


if __name__ == "__main__":
    main()
