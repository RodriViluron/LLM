"""Genera la tabla de CPU y GPU por gama (rag/docs/tabla_cpu_gpu_por_gama.md) desde los criterios de gamas.md.

Problema 1: la tabla estaba vacía y la gama de todo daba «sin datos». Los criterios ya estaban escritos
en rag/docs/gamas.md (qué línea de procesador y qué placas de video entran en cada gama); acá se pasan
a código **una sola vez** (`CRITERIOS_GAMA`) y se aplican al catálogo para escribir la tabla. El mismo
criterio lo usa evaluacion/reparto_presupuesto.py.

Así hay una sola fuente de verdad:
- El documento lo indexa el RAG: lo que el agente explica sale de ahí.
- gamas.py lo lee para clasificar: lo que el código aplica sale de ahí.

El generador asigna **solo lo que dicen los criterios**. Lo que no encaja (ningún criterio, dos gamas,
socket viejo, modelo ilegible) va a «Pendientes de decidir»: lo decide el grupo con la tienda y lo
escribe en la sección manual, que se conserva al regenerar y manda sobre lo generado.

Uso:  python -m mcp_tienda.armado.tabla_gamas [--catalogo datos/catalogo_real.sqlite] [--escribir-doc]
"""

import argparse
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from mcp_tienda.armado.gamas import GAMAS, clasificar_gama, ruta_tabla
from mcp_tienda.config import RAIZ

# Qué CPU y GPU entran en cada gama, según rag/docs/gamas.md. Las expresiones se aplican al nombre del
# producto en mayúsculas y con los espacios repetidos colapsados. `sockets`: solo procesadores de esas
# plataformas (así un Core i5 de 2012 no cae en gama media por llamarse «i5»). `gpu: None` = la gama
# no lleva placa de video.
CRITERIOS_GAMA = {
    "baja": {"cpu": r"CELERON|PENTIUM|CORE I3|RYZEN 3", "sockets": ["AM4", "LGA1200", "LGA1700"],
             "gpu": None},
    "media": {"cpu": r"CORE I5|RYZEN 5", "sockets": ["AM4", "AM5", "LGA1200", "LGA1700"],
              "gpu": r"GTX ?1650|RTX ?3050|RX ?580|RX ?7600|RTX ?5050"},
    "alta": {"cpu": r"CORE I7|CORE I9|RYZEN 7|RYZEN 9 (?!99[05]0X)", "sockets": ["AM4", "AM5", "LGA1700"],
             "gpu": r"RTX ?5060\b|RTX ?5060 ?TI|RTX ?5070\b"},
    "premium": {"cpu": r"ULTRA 9|RYZEN 9 99[05]0X", "sockets": ["AM5", "LGA1851"],
                "gpu": r"RTX ?5070\b|RTX ?5070 ?TI"},
}
assert tuple(CRITERIOS_GAMA) == GAMAS

MARCA_MANUAL_INICIO = "<!-- MANUAL: INICIO (esta sección se conserva al regenerar; lo que se escribe acá manda) -->"
MARCA_MANUAL_FIN = "<!-- MANUAL: FIN -->"

MANUAL_POR_DEFECTO = """\
Filas que el grupo agrega o corrige a mano: modelos viejos que aparecen en los requisitos de juegos y
programas (GTX 1060, Core i5-4460, Ryzen 5 1600) y las decisiones de «Pendientes de decidir». Si un
modelo ya está en la tabla generada, la fila de acá la reemplaza.

| componente | modelo | gama | puntaje |
|---|---|---|---|
"""


def _mayusculas(nombre: str) -> str:
    return " ".join(nombre.upper().split())


# --- Leer el modelo del nombre del producto -------------------------------------------

_SUFIJO_GPU = {"TI": " Ti", "XT": " XT", "XTX": " XTX", "SUPER": " Super"}


def modelo_de(nombre: str, componente: str) -> str | None:
    """Modelo escrito como va en la tabla («Core i5-12400F», «RTX 5060 Ti»); None si no se sabe leer."""
    n = _mayusculas(nombre)
    if componente == "cpu":
        if m := re.search(r"\bCORE I([3579]) (\d{4,5}[A-Z]*)\b", n):
            return f"Core i{m[1]}-{m[2]}"
        if m := re.search(r"\bULTRA ([579]) (\d{3}[A-Z]*)\b", n):
            return f"Ultra {m[1]} {m[2]}"
        if m := re.search(r"\bRYZEN ([3579]) (\d{4}[A-Z0-9]*)\b", n):
            return f"Ryzen {m[1]} {m[2]}"
        if m := re.search(r"\b(CELERON|PENTIUM)\b.*?\b([GJN]\d{3,4}[A-Z]*)\b", n):
            return f"{m[1].capitalize()} {m[2]}"
        if m := re.search(r"\bXEON (\w+)", n):
            return f"Xeon {m[1]}"
        return None
    if m := re.search(r"\b(GTX|GT|RTX|RX) ?(\d{3,4})(TI|XTX|XT|SUPER)?\b", n):
        return f"{m[1]} {m[2]}{_SUFIJO_GPU.get(m[3] or '', '')}"
    if m := re.search(r"\bQUADRO (P\d{3,4})\b", n):
        return f"Quadro {m[1]}"
    return None


# --- Asignar gamas -------------------------------------------------------------------------

def gamas_por_criterio(producto: dict) -> list[str]:
    """Gamas cuyo criterio incluye al producto (puede ser ninguna o más de una)."""
    n, componente = _mayusculas(producto["nombre"]), producto["categoria"]
    gamas = []
    for gama, criterio in CRITERIOS_GAMA.items():
        patron = criterio[componente]
        if patron is None or not re.search(patron, n):
            continue
        if componente == "cpu" and producto.get("socket") not in criterio["sockets"]:
            continue
        gamas.append(gama)
    return gamas


def _motivo(producto: dict) -> str:
    """Por qué un producto no recibe gama (solo para los que no la reciben)."""
    n, componente = _mayusculas(producto["nombre"]), producto["categoria"]
    por_nombre = [g for g, c in CRITERIOS_GAMA.items() if c[componente] and re.search(c[componente], n)]
    if componente == "cpu" and por_nombre:
        return (f"la línea encaja en gama {', '.join(por_nombre)}, pero su socket "
                f"({producto.get('socket') or 'sin dato'}) no está entre los de esa gama")
    if len(por_nombre) > 1:
        return f"entra en dos gamas: {' y '.join(por_nombre)}"
    return "ningún criterio de gamas.md lo incluye"


def armar_tabla(productos: list[dict]) -> tuple[list[dict], list[dict]]:
    """(filas, pendientes) para la tabla, a partir de los productos de CPU y GPU.

    Fila: {componente, modelo, gama, productos}. Pendiente: {componente, modelo, motivo, ejemplo}.
    """
    por_modelo: dict[tuple[str, str], dict] = {}
    pendientes: dict[tuple[str, str], dict] = {}
    for p in productos:
        componente = p["categoria"]
        modelo = modelo_de(p["nombre"], componente)
        if modelo is None:
            clave = (componente, _mayusculas(p["nombre"]))
            pendientes[clave] = {"componente": componente, "modelo": clave[1],
                                 "motivo": "no se pudo leer el modelo del nombre", "ejemplo": p["codigo"]}
            continue
        gamas = gamas_por_criterio(p)
        clave = (componente, modelo)
        if len(gamas) != 1:
            pendientes.setdefault(clave, {"componente": componente, "modelo": modelo,
                                          "motivo": _motivo(p) if not gamas else
                                          f"entra en dos gamas: {' y '.join(gamas)}", "ejemplo": p["codigo"]})
            continue
        fila = por_modelo.setdefault(clave, {"componente": componente, "modelo": modelo, "gama": gamas[0],
                                             "productos": 0})
        if fila["gama"] != gamas[0]:   # el mismo modelo con criterios distintos: que lo decida el grupo
            pendientes[clave] = {"componente": componente, "modelo": modelo, "ejemplo": p["codigo"],
                                 "motivo": f"productos del mismo modelo caen en {fila['gama']} y {gamas[0]}"}
        fila["productos"] += 1
    filas = [f for clave, f in por_modelo.items() if clave not in pendientes]
    orden = {g: i for i, g in enumerate(GAMAS)}
    filas.sort(key=lambda f: (f["componente"], orden[f["gama"]], f["modelo"]))
    return filas, sorted(pendientes.values(), key=lambda p: (p["componente"], p["modelo"]))


# --- Documento -------------------------------------------------------------------------------

def _seccion_manual(ruta: Path) -> str:
    if ruta.exists():
        texto = ruta.read_text(encoding="utf-8")
        if MARCA_MANUAL_INICIO in texto and MARCA_MANUAL_FIN in texto:
            return texto[texto.index(MARCA_MANUAL_INICIO): texto.index(MARCA_MANUAL_FIN) + len(MARCA_MANUAL_FIN)]
    return f"{MARCA_MANUAL_INICIO}\n{MANUAL_POR_DEFECTO}{MARCA_MANUAL_FIN}"


def _tabla_md(filas: list[dict]) -> list[str]:
    lineas = ["| componente | modelo | gama | puntaje |", "|---|---|---|---|"]
    lineas += [f"| {f['componente']} | {f['modelo']} | {f['gama']} | |" for f in filas]
    return lineas


def escribir_documento(ruta: Path, filas: list[dict], pendientes: list[dict], fecha: str | None = None) -> None:
    """Escribe el documento. Conserva la sección manual y la pone al final, para que mande."""
    manual = _seccion_manual(ruta)
    fecha = fecha or date.today().isoformat()
    titulos = {"cpu": "Procesadores (CPU)", "gpu": "Placas de video (GPU)"}
    lineas = [
        "# Tabla de referencia de CPU y GPU por gama",
        "",
        "> **Título:** Tabla de referencia de CPU y GPU por gama  ",
        f"> **Fecha:** {fecha}  ",
        "> **Fuente:** generada por el Grupo 10 desde los criterios de `gamas.md` aplicados al catálogo de la "
        "tienda (`python -m mcp_tienda.armado.tabla_gamas --escribir-doc`). La sección «Agregados y correcciones "
        "a mano» la escribe el grupo.",
        "",
        "## Cómo leer esta tabla",
        "",
        "Cada fila dice en qué gama (baja, media, alta o premium) está un modelo de procesador o de placa de "
        "video. El criterio es el de `gamas.md`: la gama baja usa Celeron, Pentium, Core i3 o Ryzen 3; la media, "
        "Core i5 o Ryzen 5; la alta, Core i7, Core i9, Ryzen 7 o Ryzen 9; la premium, Core Ultra 9 o Ryzen 9 "
        "9900X / 9950X. Solo cuentan los procesadores de plataformas actuales (AM4, AM5, LGA1200, LGA1700, "
        "LGA1851). Placas de video: gama media GTX 1650, RTX 3050, RX 580, RX 7600 o RTX 5050; alta RTX 5060, "
        "RTX 5060 Ti o RTX 5070; premium RTX 5070 o RTX 5070 Ti. La gama baja no lleva placa de video.",
        "",
        "El asistente usa esta tabla para filtrar productos por gama y para ubicar los requisitos de un juego o "
        "programa en una gama. Un modelo que no está en la tabla no tiene gama: el asistente lo dice y no la "
        "adivina.",
        "",
    ]
    # Una subsección por componente y gama: así cada fragmento del RAG habla de una sola gama (problema 5).
    nombres = {"cpu": "Procesadores", "gpu": "Placas de video"}
    for componente in ("cpu", "gpu"):
        lineas += [f"## {titulos[componente]}", ""]
        for gama in GAMAS:
            del_grupo = [f for f in filas if f["componente"] == componente and f["gama"] == gama]
            if del_grupo:
                lineas += [f"### {nombres[componente]} de gama {gama}", "", *_tabla_md(del_grupo), ""]
    lineas += ["## Pendientes de decidir", ""]
    if pendientes:
        lineas += ["Estos productos del catálogo no tienen gama todavía. Para asignarla, agregar la fila en la "
                   "sección de abajo.", ""]
        lineas += [f"- {titulos[p['componente']].split(' (')[0]}: **{p['modelo']}**"
                   f"{' (' + p['ejemplo'] + ')' if p.get('ejemplo') else ''}: {p['motivo']}." for p in pendientes]
    else:
        lineas.append("No hay pendientes.")
    lineas += ["", "## Agregados y correcciones a mano", "", manual, ""]
    ruta.write_text("\n".join(lineas), encoding="utf-8")


# --- Catálogo y consola --------------------------------------------------------------------------

def leer_productos(catalogo: Path) -> list[dict]:
    conexion = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True)
    productos = []
    for codigo, nombre, categoria, atributos in conexion.execute(
            "SELECT codigo, nombre, categoria, atributos FROM productos WHERE categoria IN ('cpu', 'gpu')"):
        productos.append({"codigo": codigo, "nombre": nombre, "categoria": categoria,
                          **(json.loads(atributos) if atributos else {})})
    conexion.close()
    return productos


def cobertura(productos: list[dict], ruta: Path) -> dict[str, tuple[int, int]]:
    """Por componente: (productos con gama según la tabla, total)."""
    resultado = {}
    for componente in ("cpu", "gpu"):
        del_tipo = [p for p in productos if p["categoria"] == componente]
        con_gama = sum(clasificar_gama(p["nombre"], componente, ruta) is not None for p in del_tipo)
        resultado[componente] = (con_gama, len(del_tipo))
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera la tabla de CPU y GPU por gama desde gamas.md.")
    parser.add_argument("--catalogo", type=Path, default=RAIZ / "datos" / "catalogo_real.sqlite")
    parser.add_argument("--escribir-doc", action="store_true", help="escribe rag/docs/tabla_cpu_gpu_por_gama.md")
    args = parser.parse_args()

    productos = leer_productos(args.catalogo)
    destino = ruta_tabla()
    antes = cobertura(productos, destino)
    filas, pendientes = armar_tabla(productos)
    print(f"Filas generadas: {len(filas)} · pendientes de decidir: {len(pendientes)}")
    for p in pendientes:
        print(f"  pendiente {p['componente']}: {p['modelo']} ({p['ejemplo']}): {p['motivo']}")
    if not args.escribir_doc:
        print("(No se escribió nada: agregá --escribir-doc.)")
        return
    escribir_documento(destino, filas, pendientes)
    despues = cobertura(productos, destino)
    for componente in ("cpu", "gpu"):
        print(f"{componente}: con gama antes {antes[componente][0]}/{antes[componente][1]}, "
              f"después {despues[componente][0]}/{despues[componente][1]}")
    # Control: cada fila generada tiene que reconocer a los productos de los que salió.
    sin_reconocer = [p["codigo"] for p in productos if modelo_de(p["nombre"], p["categoria"])
                     and len(gamas_por_criterio(p)) == 1
                     and clasificar_gama(p["nombre"], p["categoria"], destino) is None]
    if sin_reconocer:
        raise SystemExit(f"Filas que no reconocen a su producto: {sin_reconocer}")
    print(f"Escrito {destino}. Reindexá el RAG: uv run python -m rag.ingest")


if __name__ == "__main__":
    main()
