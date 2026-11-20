"""Mide qué tan bien andan las reglas de compatibilidad con un catálogo (por defecto, el real).

Tres mediciones, todas sobre productos con stock:

1. Cobertura: para cada atributo que usan las reglas, en cuántos productos tiene dato (no nulo).
   Que la clave exista no alcanza: muchos productos la traen con valor nulo.
2. Simulación: arma N PCs al azar «razonables» (CPU y placa del mismo socket, RAM del tipo de la
   placa, a veces placa de video y cooler) y cuenta qué da cada regla. Lo importante es el
   porcentaje de «sin datos»: cada uno es un armado que el agente no puede confirmar.
   Además cuenta los **falsos compatibles**: armados con una falla física comprobable (con los
   datos del catálogo) que igual se podrían confirmar (misma decisión que el botón Confirmar). Las comprobaciones de
   `fallas_fisicas` están escritas aparte de `reglas.py` a propósito: son el control.
3. Candidatos: para cada fuente con stock, cuántas placas de video devuelve la búsqueda de
   candidatos compatibles (con la CPU más común). Si da 0, el armado se traba.

Uso:
    uv run python -m evaluacion.reglas_catalogo
    uv run python -m evaluacion.reglas_catalogo --db datos/catalogo.sqlite --n 2000 --semilla 0
"""

import argparse
import json
import random
from collections import Counter, defaultdict

from armado import motivos_para_no_confirmar
from mcp_tienda.armado.candidatos import filtros_compatibles
from mcp_tienda.armado.reglas import CONSUMO_BASE_W, MARGEN_FUENTE, verificar_compatibilidad
from mcp_tienda.catalogo import Catalogo
from mcp_tienda.config import RAIZ
from mcp_tienda.ingesta.extraccion import SOCKETS as SOCKETS_ARMADO
from mcp_tienda.modelos import Configuracion, Producto

DB_POR_DEFECTO = RAIZ / "datos" / "catalogo_real.sqlite"
SALIDA = RAIZ / "evaluacion" / "resultados" / "reglas_catalogo.json"
CATEGORIAS = ("cpu", "motherboard", "ram", "gpu", "almacenamiento", "fuente", "gabinete", "cooler")

# Atributos que usan (o van a usar) las reglas y los filtros de candidatos.
ATRIBUTOS_USADOS = {
    "cpu": ["socket", "tdp_w", "consumo_max_w", "generacion", "incluye_cooler", "video_integrado"],
    "motherboard": ["socket", "tipo_ram", "formato", "generaciones", "ranuras_ram", "puertos_sata", "ranuras_m2"],
    "ram": ["tipo", "modulos", "formato_modulo"],
    "gpu": ["consumo_w", "largo_mm", "fuente_recomendada_w", "conectores_energia"],
    "almacenamiento": ["tipo", "conexion"],
    "fuente": ["potencia_w", "conectores_pcie"],
    "gabinete": ["formatos_admitidos", "largo_max_gpu_mm", "incluye_fuente", "potencia_fuente_w"],
    "cooler": ["sockets", "potencia_enfriamiento_w"],
}


def productos_con_stock(catalogo: Catalogo) -> dict[str, list[Producto]]:
    """Todos los productos con stock por categoría (`buscar` corta en 50, por eso va por SQL)."""
    with catalogo._conectar() as conn:
        filas = conn.execute("SELECT * FROM productos WHERE stock > 0 ORDER BY codigo").fetchall()
    salida: dict[str, list[Producto]] = {cat: [] for cat in CATEGORIAS}
    for fila in filas:
        if fila["categoria"] in salida:
            salida[fila["categoria"]].append(catalogo._a_producto(fila))
    return salida


def cobertura(productos: dict[str, list[Producto]]) -> dict:
    salida = {}
    for cat, atributos in ATRIBUTOS_USADOS.items():
        lista = productos[cat]
        salida[cat] = {"productos": len(lista)}
        for a in atributos:
            con_dato = sum(1 for p in lista if p.atributos.get(a) is not None)
            salida[cat][a] = round(con_dato / len(lista), 3) if lista else None
    return salida


def fallas_fisicas(c: dict[str, Producto], q: dict[str, int] | None = None) -> list[str]:
    """Fallas comprobables con los datos del catálogo. Si falta un dato, no se cuenta como falla.

    `q` son las cantidades por lugar (si falta, 1).
    """
    q = q or {}
    a = {slot: p.atributos for slot, p in c.items()}
    cpu, placa, ram = a["cpu"], a["motherboard"], a["ram"]
    fallas = []
    if ram.get("modulos") and placa.get("ranuras_ram") and ram["modulos"] * q.get("ram", 1) > placa["ranuras_ram"]:
        fallas.append("ranuras_ram")
    discos = {"M.2": 0, "SATA": 0}
    for lugar in ("almacenamiento", "almacenamiento_extra"):
        if lugar in c and a[lugar].get("conexion") in discos:
            discos[a[lugar]["conexion"]] += q.get(lugar, 1)
    if (placa.get("ranuras_m2") is not None and discos["M.2"] > placa["ranuras_m2"]) or \
            (placa.get("puertos_sata") is not None and discos["SATA"] > placa["puertos_sata"]):
        fallas.append("puertos_almacenamiento")
    if ram.get("formato_modulo") not in (None, "DIMM"):
        fallas.append("modulo_ram")
    if cpu.get("generacion") and placa.get("generaciones") and cpu["generacion"] not in placa["generaciones"]:
        fallas.append("generacion_cpu_placa")
    if "gpu" not in c and cpu.get("video_integrado") == "no":
        fallas.append("video")
    if "cooler" not in c and cpu.get("incluye_cooler") == "no":
        fallas.append("cooler")
    if "cooler" in c:
        disipa, consume = a["cooler"].get("potencia_enfriamiento_w"), cpu.get("consumo_max_w")
        if disipa is not None and consume is not None and disipa < consume:
            fallas.append("potencia_cooler")
    if "fuente" in c and cpu.get("consumo_max_w") is not None:
        requerido = (cpu["consumo_max_w"] + CONSUMO_BASE_W) * (1 + MARGEN_FUENTE)
        if "gpu" in c:
            recomendada = a["gpu"].get("fuente_recomendada_w")
            requerido = max(requerido, recomendada) if recomendada is not None else None
        if requerido is not None and a["fuente"].get("potencia_w") is not None \
                and a["fuente"]["potencia_w"] < requerido:
            fallas.append("potencia_fuente")
    return fallas


def armado_al_azar(productos: dict[str, list[Producto]],
                   azar: random.Random) -> tuple[dict[str, Producto], dict[str, int]] | None:
    # Solo plataformas que el armado ofrece (los sockets viejos se guardan, pero no se arman).
    cpus = [p for p in productos["cpu"] if p.atributos.get("socket") in SOCKETS_ARMADO]
    cpu = azar.choice(cpus)
    placas = [p for p in productos["motherboard"]
              if p.atributos.get("socket") == cpu.atributos["socket"] and p.atributos.get("tipo_ram")]
    if not placas:
        return None
    placa = azar.choice(placas)
    rams = [p for p in productos["ram"] if p.atributos.get("tipo") == placa.atributos["tipo_ram"]]
    if not rams:
        return None
    c = {"cpu": cpu, "motherboard": placa, "ram": azar.choice(rams)}
    for cat in ("almacenamiento", "fuente", "gabinete"):
        c[cat] = azar.choice(productos[cat])
    if azar.random() < 0.6:
        c["gpu"] = azar.choice(productos["gpu"])
    if azar.random() < 0.4:
        c["cooler"] = azar.choice(productos["cooler"])
    # Cantidades: a veces dos (o cuatro) módulos de RAM y un segundo disco, como pide la gama alta.
    q = {"ram": azar.choice([1, 2, 2, 4])}
    if azar.random() < 0.4:
        c["almacenamiento_extra"] = azar.choice(productos["almacenamiento"])
        q["almacenamiento_extra"] = azar.choice([1, 1, 2])
    return c, {s: n for s, n in q.items() if n != 1}


def simular(productos: dict[str, list[Producto]], n: int, semilla: int) -> dict:
    azar = random.Random(semilla)
    estados: dict[str, Counter] = defaultdict(Counter)
    generales: Counter = Counter()
    falsos: Counter = Counter()
    hechos = confirmables = 0
    while hechos < n:
        armado = armado_al_azar(productos, azar)
        if armado is None:
            continue
        c, q = armado
        hechos += 1
        reporte = verificar_compatibilidad(Configuracion(componentes=c, cantidades=q))
        for r in reporte.resultados:
            estados[r.regla][r.estado] += 1
        generales[reporte.estado_general] += 1
        if se_puede_confirmar(c, q, reporte):
            confirmables += 1
            for falla in fallas_fisicas(c, q):
                falsos[falla] += 1
    return {
        "armados": n,
        "por_regla": {regla: {e: round(k / sum(cnt.values()), 3) for e, k in cnt.items()} | {"n": sum(cnt.values())}
                      for regla, cnt in estados.items()},
        "estado_general": {e: round(k / n, 3) for e, k in generales.items()},
        "se_pueden_confirmar": round(confirmables / n, 3),
        "falsos_compatibles": {f: round(k / n, 3) for f, k in falsos.most_common()},
    }


def se_puede_confirmar(c: dict[str, Producto], q: dict[str, int], reporte) -> bool:
    """Lo mismo que decide el botón Confirmar (armado.motivos_para_no_confirmar)."""
    config = {"componentes": {s: p.model_dump() for s, p in c.items()}, "cantidades": q,
              "reporte": reporte.como_dict()}
    return not motivos_para_no_confirmar(config)


def candidatos_gpu(catalogo: Catalogo, productos: dict[str, list[Producto]]) -> dict:
    """Placas de video candidatas con cada fuente elegida (y la CPU más común)."""
    cpu = next((p for p in productos["cpu"] if "12400F" in p.nombre), productos["cpu"][0])
    conteos = []
    for fuente in productos["fuente"]:
        filtros, _ = filtros_compatibles("gpu", {"cpu": cpu, "fuente": fuente})
        conteos.append(len(catalogo.buscar(categoria="gpu", atributos=filtros, limite=10_000)))
    return {"cpu": cpu.codigo, "fuentes": len(conteos), "fuentes_con_0_gpu": sum(1 for k in conteos if k == 0),
            "gpu_con_stock": len(productos["gpu"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(DB_POR_DEFECTO))
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--semilla", type=int, default=0)
    args = parser.parse_args()

    catalogo = Catalogo(args.db)
    productos = productos_con_stock(catalogo)
    resultado = {
        "db": args.db,
        "cobertura": cobertura(productos),
        "simulacion": simular(productos, args.n, args.semilla),
        "candidatos_gpu": candidatos_gpu(catalogo, productos),
    }

    print("== Cobertura (productos con stock que tienen el dato)")
    for cat, datos in resultado["cobertura"].items():
        partes = [f"{a} {v:.0%}" for a, v in datos.items() if a != "productos" and v is not None]
        print(f"  {cat} ({datos['productos']}): " + ", ".join(partes))
    sim = resultado["simulacion"]
    print(f"\n== Simulación: {sim['armados']} armados al azar")
    for regla, datos in sim["por_regla"].items():
        partes = [f"{e} {v:.0%}" for e, v in datos.items() if e != "n"]
        print(f"  {regla:26s} " + "  ".join(partes) + f"  (n={datos['n']})")
    print("  estado general: " + "  ".join(f"{e} {v:.0%}" for e, v in sim["estado_general"].items()))
    print(f"  se pueden confirmar: {sim['se_pueden_confirmar']:.0%}")
    print("  falsos compatibles (se puede confirmar y tiene una falla física): "
          + (", ".join(f"{f} {v:.0%}" for f, v in sim["falsos_compatibles"].items()) or "ninguno"))
    cg = resultado["candidatos_gpu"]
    print(f"\n== Candidatos de GPU con una fuente elegida: {cg['fuentes_con_0_gpu']} de {cg['fuentes']} fuentes "
          f"dejan 0 placas de video (hay {cg['gpu_con_stock']} con stock)")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalle en {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
