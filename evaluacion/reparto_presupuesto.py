"""Reparto del presupuesto por componente, medido sobre el catálogo real de la tienda.

Pregunta que responde: de lo que cuesta una PC de cada gama, ¿qué parte se lleva cada componente?
En vez de tomar porcentajes de internet, arma miles de PCs compatibles con productos y precios
reales de Todo Computación y mira cuánto pesa cada pieza en el total.

Cómo lo hace, para cada gama:
1. Elige al azar un procesador de los que la gama admite (CRITERIOS, tomados de rag/docs/gamas.md).
2. Completa el armado con piezas compatibles: placa madre del mismo socket y generación, memoria
   del tipo de la placa hasta la capacidad de la gama, disco, placa de video (si la gama lleva),
   fuente que cubra lo que pide la placa de video, gabinete donde entre la placa madre y cooler
   si el procesador no lo trae o la gama lo pide.
3. Calcula qué porcentaje del total es cada pieza.
4. Repite `--muestras` veces e informa, por componente, la mediana y el rango central (P25 a P75).

Los porcentajes salen de los precios del día: hay que volver a correrlo cuando cambian.

Uso:
    uv run python -m evaluacion.reparto_presupuesto                    muestra la tabla
    uv run python -m evaluacion.reparto_presupuesto --escribir-doc     además regenera rag/docs/reparto_presupuesto.md
    uv run python -m evaluacion.reparto_presupuesto --solo-con-stock   usa solo productos con stock
"""

import argparse
import json
import random
import re
import sqlite3
import statistics
from datetime import date
from pathlib import Path

from mcp_tienda.armado.tabla_gamas import CRITERIOS_GAMA as GAMA
from mcp_tienda.config import RAIZ

DB_POR_DEFECTO = RAIZ / "datos" / "catalogo_real.sqlite"
DOC = RAIZ / "rag" / "docs" / "reparto_presupuesto.md"
RESULTADOS = RAIZ / "evaluacion" / "resultados" / "reparto_presupuesto.json"

COMPONENTES = ["gpu", "ram", "cpu", "motherboard", "disco", "disco_extra", "fuente", "gabinete", "cooler"]

NOMBRES = {"gpu": "Placa de video", "ram": "Memoria RAM", "cpu": "Procesador", "motherboard": "Placa madre",
           "disco": "Disco (SSD M.2 NVMe o SSD 2,5\")", "disco_extra": "Disco secundario (SSD 2,5\" o HDD)",
           "fuente": "Fuente", "gabinete": "Gabinete", "cooler": "Cooler"}

# Qué entra en cada gama. Procesadores, sockets y placas de video salen de CRITERIOS_GAMA (los mismos que
# generan la tabla de gamas, tomados de rag/docs/gamas.md); el resto es el criterio del
# grupo y se puede cambiar acá. `gabinete` y `cooler` son franjas de precio (0 = el más barato,
# 1 = el más caro) dentro de los que sirven para ese armado.
CRITERIOS = {
    "baja": {
        "titulo": "Gama baja",
        "resumen": "procesador con video integrado, 8 GB DDR4, sin placa de video",
        "cpu": GAMA["baja"]["cpu"], "sockets": GAMA["baja"]["sockets"],
        "solo_con_video": True, "ddr": ["DDR4"], "ram_gb": [8], "gpu": GAMA["baja"]["gpu"], "disco_gb": (240, 512),
        "discos": ["NVMe", "SSD SATA"],
        "chipsets": "AH", "fuente_min_w": 500, "fuente_ventana_w": 100, "fuente_certificada": False,
        "gabinete": (0.0, 1 / 3), "cooler": "si_falta", "cooler_franja": (0.0, 1 / 3),
    },
    "media": {
        "titulo": "Gama media",
        "resumen": "16 GB de memoria y placa de video de entrada",
        "cpu": GAMA["media"]["cpu"], "sockets": GAMA["media"]["sockets"],
        "solo_con_video": False, "ddr": ["DDR4", "DDR5"], "ram_gb": [16],
        "gpu": GAMA["media"]["gpu"], "disco_gb": (512, 1000), "discos": ["NVMe"],
        "chipsets": "AHB", "fuente_min_w": 500, "fuente_ventana_w": 150, "fuente_certificada": False,
        "gabinete": (0.0, 2 / 3), "cooler": "si_falta", "cooler_franja": (0.0, 1 / 3),
    },
    "alta": {
        "titulo": "Gama alta",
        "resumen": "32 GB DDR4 o DDR5 y placa de video media o alta",
        "cpu": GAMA["alta"]["cpu"], "sockets": GAMA["alta"]["sockets"],
        "solo_con_video": False, "ddr": ["DDR4", "DDR5"], "ram_gb": [32],
        "gpu": GAMA["alta"]["gpu"], "disco_gb": (1000, 2000), "discos": ["NVMe"],
        "disco_extra": {"discos": ["SSD SATA", "HDD"], "gb": (1000, 2000)},
        "chipsets": "BXZ", "fuente_min_w": 650, "fuente_ventana_w": 200, "fuente_certificada": True,
        "gabinete": (1 / 3, 1.0), "cooler": "siempre", "cooler_franja": (0.0, 2 / 3),
    },
    "premium": {
        "titulo": "Gama premium",
        "resumen": "64 GB DDR5 y placa de video RTX serie 50 de las más potentes",
        "cpu": GAMA["premium"]["cpu"], "sockets": GAMA["premium"]["sockets"],
        "solo_con_video": False, "ddr": ["DDR5"], "ram_gb": [64],
        "gpu": GAMA["premium"]["gpu"], "disco_gb": (2000, 2000), "discos": ["NVMe"],
        "disco_extra": {"discos": ["SSD SATA", "HDD"], "gb": (1000, 2000)},
        "chipsets": "XZ", "fuente_min_w": 750, "fuente_ventana_w": 250, "fuente_certificada": True,
        "gabinete": (2 / 3, 1.0), "cooler": "siempre", "cooler_franja": (0.5, 1.0),
    },
}


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

def leer_catalogo(ruta: Path, solo_con_stock: bool = False) -> dict[str, list[dict]]:
    """Las piezas de PC del catálogo, por categoría: {codigo, nombre, precio, stock, atributos...}."""
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Cargá el catálogo real: "
                         "uv run python -m mcp_tienda.ingesta.cargar --fuente api --db datos/catalogo_real.sqlite")
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    piezas: dict[str, list[dict]] = {}
    consulta = "SELECT codigo, nombre, categoria, precio, stock, atributos FROM productos WHERE precio > 0"
    for fila in conexion.execute(consulta):
        if solo_con_stock and fila["stock"] <= 0:
            continue
        pieza = {"codigo": fila["codigo"], "nombre": " ".join(fila["nombre"].split()), "precio": fila["precio"],
                 "stock": fila["stock"], **json.loads(fila["atributos"])}
        piezas.setdefault(fila["categoria"], []).append(pieza)
    conexion.close()
    return piezas


def _franja(candidatos: list[dict], desde: float, hasta: float) -> list[dict]:
    """Los candidatos cuyo precio cae en esa franja (0 = el más barato, 1 = el más caro)."""
    ordenados = sorted(candidatos, key=lambda p: p["precio"])
    if not ordenados:
        return []
    inicio = min(int(len(ordenados) * desde), len(ordenados) - 1)
    fin = max(inicio + 1, round(len(ordenados) * hasta))
    return ordenados[inicio:fin]


# ---------------------------------------------------------------------------
# Un armado al azar, compatible
# ---------------------------------------------------------------------------

def armar(piezas: dict[str, list[dict]], c: dict, azar: random.Random) -> dict[str, tuple[dict, int]] | None:
    """Devuelve {componente: (producto, cantidad)} o None si con esa combinación no se pudo completar."""
    cpus = [p for p in piezas.get("cpu", []) if re.search(c["cpu"], p["nombre"]) and p.get("socket") in c["sockets"]
            and (not c["solo_con_video"] or p.get("video_integrado") == "si")]
    if not cpus:
        return None
    cpu = azar.choice(cpus)

    placas = [p for p in piezas.get("motherboard", [])
              if p.get("socket") == cpu["socket"] and cpu.get("generacion") in (p.get("generaciones") or [])
              and p.get("tipo_ram") in c["ddr"] and p.get("formato") and p.get("ranuras_ram")
              and (m := re.search(r"\b([ABHXZ])\d{3}", p["nombre"])) and m.group(1) in c["chipsets"]]
    if not placas:
        return None
    placa = azar.choice(placas)

    objetivo = azar.choice(c["ram_gb"])
    memorias = [(p, n) for p in piezas.get("ram", []) for n in (1, 2, 4)
                if p.get("formato_modulo") == "DIMM" and p.get("tipo") == placa["tipo_ram"]
                and p.get("capacidad_gb") and p["capacidad_gb"] * n == objetivo
                and (p.get("modulos") or 1) * n <= placa["ranuras_ram"]]
    discos = [p for p in piezas.get("almacenamiento", [])
              if p.get("tipo") in c["discos"] and c["disco_gb"][0] <= (p.get("capacidad_gb") or 0) <= c["disco_gb"][1]]
    if not memorias or not discos:
        return None
    if not placa.get("ranuras_m2"):
        # sin ranura M.2 solo sirve un SSD SATA de 2,5"
        discos = [d for d in discos if d.get("tipo") == "SSD SATA"]
        if not discos:
            return None
    armado = {"cpu": (cpu, 1), "motherboard": (placa, 1), "ram": azar.choice(memorias),
              "disco": (azar.choice(discos), 1)}

    if c.get("disco_extra"):
        # Gama alta y premium: un segundo disco SATA (SSD 2,5" o HDD). Necesita un puerto SATA libre en la placa.
        extra = c["disco_extra"]
        secundarios = [p for p in piezas.get("almacenamiento", [])
                       if p.get("tipo") in extra["discos"] and p.get("conexion") == "SATA"
                       and extra["gb"][0] <= (p.get("capacidad_gb") or 0) <= extra["gb"][1]]
        if not secundarios or (placa.get("puertos_sata") or 0) < 1:
            return None
        armado["disco_extra"] = (azar.choice(secundarios), 1)

    pide_w = 0
    if c["gpu"]:
        placas_video = [p for p in piezas.get("gpu", [])
                        if re.search(c["gpu"], p["nombre"]) and p.get("fuente_recomendada_w")]
        if not placas_video:
            return None
        gpu = azar.choice(placas_video)
        armado["gpu"] = (gpu, 1)
        pide_w = gpu["fuente_recomendada_w"]
    elif cpu.get("video_integrado") != "si":
        return None   # sin placa de video, el procesador tiene que traer video

    minimo = max(pide_w, c["fuente_min_w"])
    fuentes = [p for p in piezas.get("fuente", [])
               if p.get("potencia_w") and minimo <= p["potencia_w"] <= minimo + c["fuente_ventana_w"]
               and (not c["fuente_certificada"] or p.get("certificacion"))]
    gabinetes = [p for p in piezas.get("gabinete", [])
                 if p.get("incluye_fuente") == "no" and placa["formato"] in (p.get("formatos_admitidos") or [])]
    gabinetes = _franja(gabinetes, *c["gabinete"])
    if not fuentes or not gabinetes:
        return None
    armado["fuente"] = (azar.choice(fuentes), 1)
    armado["gabinete"] = (azar.choice(gabinetes), 1)

    if c["cooler"] == "siempre" or cpu.get("incluye_cooler") != "si":
        consumo = cpu.get("consumo_max_w") or cpu.get("tdp_w") or 0
        coolers = [p for p in piezas.get("cooler", [])
                   if cpu["socket"] in (p.get("sockets") or []) and (p.get("potencia_enfriamiento_w") or 0) >= consumo]
        coolers = _franja(coolers, *c["cooler_franja"])
        if not coolers:
            return None
        armado["cooler"] = (azar.choice(coolers), 1)
    return armado


# ---------------------------------------------------------------------------
# Medición
# ---------------------------------------------------------------------------

def _percentil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * q
    abajo, arriba = int(posicion), min(int(posicion) + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


def medir(piezas: dict[str, list[dict]], muestras: int = 5000, semilla: int = 7) -> dict:
    resultado = {}
    for gama, criterio in CRITERIOS.items():
        azar = random.Random(semilla)
        partes: dict[str, list[float]] = {comp: [] for comp in COMPONENTES}
        totales, distintos, usados = [], set(), {comp: set() for comp in COMPONENTES}
        for _ in range(muestras):
            armado = armar(piezas, criterio, azar)
            if armado is None:
                continue
            total = sum(p["precio"] * n for p, n in armado.values())
            totales.append(total)
            distintos.add(tuple(sorted((comp, p["codigo"], n) for comp, (p, n) in armado.items())))
            for comp in COMPONENTES:
                producto, cantidad = armado.get(comp, ({"precio": 0.0}, 0))
                partes[comp].append(100 * producto["precio"] * cantidad / total)
                if cantidad:
                    usados[comp].add(producto["codigo"])
        if not totales:
            resultado[gama] = {"armados": 0}
            continue
        resultado[gama] = {
            "armados": len(totales), "armados_distintos": len(distintos),
            "total": {"p25": _percentil(totales, 0.25), "mediana": statistics.median(totales),
                      "p75": _percentil(totales, 0.75)},
            "componentes": {comp: {"mediana": statistics.median(partes[comp]), "p25": _percentil(partes[comp], 0.25),
                                   "p75": _percentil(partes[comp], 0.75), "productos": len(usados[comp])}
                            for comp in COMPONENTES},
        }
    return resultado


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------

def _pesos(valor: float) -> str:
    return "$ " + f"{round(valor, -3):,.0f}".replace(",", ".")


def _porcentaje(m: dict) -> str:
    if m["p75"] < 0.5:
        return "0 %"
    return f"{m['mediana']:.0f} % (entre {m['p25']:.0f} % y {m['p75']:.0f} %)"


def imprimir(resultado: dict) -> None:
    for gama, r in resultado.items():
        if not r["armados"]:
            print(f"\n{CRITERIOS[gama]['titulo']}: no se pudo armar ninguna PC con ese criterio.")
            continue
        t = r["total"]
        print(f"\n{CRITERIOS[gama]['titulo']} — {r['armados_distintos']} armados distintos — "
              f"total típico {_pesos(t['mediana'])} (entre {_pesos(t['p25'])} y {_pesos(t['p75'])})")
        for comp in COMPONENTES:
            m = r["componentes"][comp]
            print(f"  {NOMBRES[comp]:18} {_porcentaje(m):32} {m['productos']:>3} productos")


def documento(resultado: dict, productos: int, solo_con_stock: bool) -> str:
    """El documento del RAG. Cada gama va en su propia sección corta, para que se recupere entera."""
    hoy = date.today().isoformat()
    alcance = ("solo productos con stock" if solo_con_stock
               else "productos con y sin stock (la tienda también vende a pedido)")
    lineas = [
        "# Reparto del presupuesto por componente",
        "",
        "> **Título:** Reparto del presupuesto por componente  ",
        f"> **Fecha:** {hoy}  ",
        f"> **Fuente:** precios del catálogo de Todo Computación al {hoy} ({productos} piezas de PC, {alcance}). "
        "Calculado con `evaluacion/reparto_presupuesto.py`; no usa precios de internet.",
        "",
        "## Para qué sirve",
        "",
        "Dice qué parte del presupuesto de una PC se lleva cada componente, según la gama. Sirve para repartir "
        "un presupuesto antes de elegir las piezas: con cuánto buscar el procesador, la placa de video, "
        "la memoria, etc.",
        "",
        "Los porcentajes son orientativos. Salen de armar miles de PCs compatibles con productos reales de la tienda "
        "y medir cuánto pesa cada pieza en el total. El primer número es el valor típico; entre paréntesis, el rango "
        "habitual. Cambian cuando cambian los precios: la fecha de arriba dice de cuándo son.",
        "",
    ]
    for gama, r in resultado.items():
        criterio = CRITERIOS[gama]
        lineas += [f"## Reparto del presupuesto en {criterio['titulo'].lower()}", ""]
        if not r["armados"]:
            lineas += ["Con los productos actuales no se pudo armar ninguna PC de esta gama.", ""]
            continue
        t = r["total"]
        lineas += [
            f"{criterio['titulo']}: {criterio['resumen']}. "
            f"Una PC de {criterio['titulo'].lower()} en la tienda cuesta típicamente {_pesos(t['mediana'])} "
            f"(entre {_pesos(t['p25'])} y {_pesos(t['p75'])}).",
            "",
            f"Porcentaje del presupuesto por componente en {criterio['titulo'].lower()}:",
            "",
        ]
        for comp in COMPONENTES:
            m = r["componentes"][comp]
            if comp == "gpu" and criterio["gpu"] is None:
                detalle = "0 % (usa el video integrado del procesador)"
            elif comp == "cooler" and m["p75"] < 0.5:
                detalle = "0 % (usa el cooler que trae el procesador)"
            else:
                detalle = _porcentaje(m)
            # Cada renglón nombra la gama: así se entiende solo, caiga en el fragmento que caiga.
            lineas.append(f"- {criterio['titulo']}, {NOMBRES[comp].lower()}: {detalle}")
        lineas.append("")
    lineas += [
        "## Cómo usar el reparto",
        "",
        "1. Ubicar el pedido en una gama (ver `gamas.md`).",
        "2. Multiplicar el presupuesto por el porcentaje típico de cada componente: ese es el precio de referencia "
        "para buscar esa pieza.",
        "3. Si una pieza sale más barata, lo que sobra conviene pasarlo al componente que más pesa en esa gama.",
        "4. El total real lo calcula la tienda al armar: el reparto es solo una guía para empezar.",
        "",
        "## Qué se consideró en cada gama",
        "",
        "- Gama baja: Celeron, Pentium, Core i3 o Ryzen 3 con video integrado; 8 GB DDR4; disco de 240 a 512 GB (SSD M.2 NVMe o SSD 2,5\"); "
        "fuente de 500 a 600 W; gabinete económico.",
        "- Gama media: Core i5 o Ryzen 5; 16 GB; disco M.2 NVMe de 512 GB a 1 TB; placa de video GTX 1650, RTX 3050, "
        "RX 580, RX 7600 o RTX 5050.",
        "- Gama alta: Core i7, Core i9, Ryzen 7 o Ryzen 9 con memoria DDR4 o DDR5; 32 GB; disco M.2 NVMe de 1 a 2 TB "
        "(el disco secundario SSD 2,5\" o HDD no entra en el reparto); placa de video "
        "RTX 5060, RTX 5060 Ti o RTX 5070; fuente certificada; cooler aparte.",
        "- Gama premium: Core Ultra 9 o Ryzen 9 9900X / 9950X; 64 GB DDR5; disco de 2 TB; placa de video RTX 5070 "
        "o RTX 5070 Ti; fuente certificada de 750 W o más; cooler de los más potentes.",
        "",
        "En todos los casos las piezas son compatibles entre sí: mismo socket y generación, memoria del tipo de la "
        "placa madre, fuente que cubre lo que pide la placa de video y gabinete donde entra la placa madre.",
        "",
    ]
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DB_POR_DEFECTO, help="catálogo real ya cargado (SQLite)")
    parser.add_argument("--muestras", type=int, default=5000, help="armados al azar por gama")
    parser.add_argument("--semilla", type=int, default=7)
    parser.add_argument("--solo-con-stock", action="store_true", help="usa solo productos con stock")
    parser.add_argument("--escribir-doc", action="store_true", help=f"regenera {DOC.relative_to(RAIZ)}")
    args = parser.parse_args()

    piezas = leer_catalogo(args.db, args.solo_con_stock)
    productos = sum(len(piezas.get(cat, [])) for cat in
                    ("cpu", "motherboard", "ram", "gpu", "almacenamiento", "fuente", "gabinete", "cooler"))
    resultado = medir(piezas, args.muestras, args.semilla)
    imprimir(resultado)

    RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    RESULTADOS.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nDetalle: {RESULTADOS}")
    if args.escribir_doc:
        DOC.write_text(documento(resultado, productos, args.solo_con_stock), encoding="utf-8")
        print(f"Documento del RAG: {DOC}  (después: uv run python -m rag.ingest)")


if __name__ == "__main__":
    main()
