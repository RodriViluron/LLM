"""Perfiles de uso y guía de preguntas del armado (problemas 6 y 26).

`datos/entrevista_armado.yaml` es la única fuente de «uso → gama». Desde acá se genera la sección
«Perfiles de uso» de rag/docs/caracteristicas_por_actividad.md (lo que el agente explica con el RAG) y
la va a usar la entrevista del armado (problema 26). El resto del documento es prosa escrita a mano y
no se toca: solo se reemplaza lo que está entre las marcas.

Cada perfil va en su propia subsección con la gama en el título («Perfil Juegos en 1080p: gama media»):
así la ingesta del RAG le asigna la gama en la metadata y el filtro por gama lo encuentra (problema 5).

Uso:  python -m mcp_tienda.armado.perfiles [--escribir-doc]
"""

import argparse
from functools import cache
from pathlib import Path

import yaml

from mcp_tienda.armado.gamas import GAMAS
from mcp_tienda.config import RAIZ

RUTA_ENTREVISTA = RAIZ / "datos" / "entrevista_armado.yaml"
RUTA_DOCUMENTO = RAIZ / "rag" / "docs" / "caracteristicas_por_actividad.md"
MARCA_INICIO = "<!-- PERFILES: INICIO (generado desde datos/entrevista_armado.yaml: no editar a mano) -->"
MARCA_FIN = "<!-- PERFILES: FIN -->"

NOMBRES = {"cpu": "procesador", "gpu": "placa de video", "ram": "memoria RAM", "disco": "disco",
           "motherboard": "placa madre", "fuente": "fuente", "gabinete": "gabinete", "cooler": "cooler"}


@cache
def _leer(ruta: str, _modificado: float) -> dict:
    return yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))


def cargar_entrevista(ruta: Path | None = None) -> dict:
    """Perfiles y preguntas. Se vuelve a leer si el archivo cambió."""
    ruta = ruta or RUTA_ENTREVISTA
    datos = _leer(str(ruta), ruta.stat().st_mtime)
    for clave, perfil in datos["perfiles"].items():
        if perfil["gama"] not in GAMAS:
            raise ValueError(f"El perfil {clave} tiene una gama desconocida: {perfil['gama']}")
    return datos


def bloque_de_perfiles(entrevista: dict) -> str:
    """El texto generado: una subsección por perfil, con su gama en el título."""
    lineas = [MARCA_INICIO, ""]
    if entrevista.get("estado") == "borrador":
        lineas += ["Estos perfiles son un **borrador** para revisar con el grupo y la tienda.", ""]
    lineas += ["Cada pedido se ubica en uno de estos perfiles según para qué se va a usar la PC. El perfil decide "
               "la gama y en qué componentes conviene poner más presupuesto.", ""]
    for perfil in entrevista["perfiles"].values():
        video = ("con placa de video dedicada" if perfil["gpu"]
                 else "sin placa de video (usa el video integrado del procesador)")
        pesa = ", ".join(NOMBRES[c] for c in perfil["pesa_mas"])
        lineas += [
            f"### Perfil {perfil['nombre']}: gama {perfil['gama']}",
            "",
            f"Perfil {perfil['nombre']}: una PC de gama {perfil['gama']}, con {perfil['ram_gb']} GB de RAM y {video}.",
            f"- Dónde conviene poner más presupuesto: {pesa}.",
            f"- Alcanza para: {perfil['alcanza_para']}.",
            f"- No alcanza para: {perfil['no_alcanza_para']}.",
            f"- Ejemplos: {', '.join(perfil['ejemplos'])}.",
            "",
        ]
    lineas.append(MARCA_FIN)
    return "\n".join(lineas)


def escribir_perfiles_en_documento(ruta: Path | None = None, entrevista: dict | None = None) -> None:
    """Reemplaza el bloque entre las marcas; si no hay marcas, agrega la sección «Perfiles de uso» al final."""
    ruta = ruta or RUTA_DOCUMENTO
    bloque = bloque_de_perfiles(entrevista or cargar_entrevista())
    texto = ruta.read_text(encoding="utf-8")
    if MARCA_INICIO in texto and MARCA_FIN in texto:
        inicio, fin = texto.index(MARCA_INICIO), texto.index(MARCA_FIN) + len(MARCA_FIN)
        texto = texto[:inicio] + bloque + texto[fin:]
    else:
        texto = texto.rstrip() + "\n\n## Perfiles de uso\n\n" + bloque + "\n"
    ruta.write_text(texto, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera la sección «Perfiles de uso» desde entrevista_armado.yaml.")
    parser.add_argument("--escribir-doc", action="store_true")
    entrevista = cargar_entrevista()
    print(f"{len(entrevista['perfiles'])} perfiles, {len(entrevista['preguntas'])} preguntas "
          f"(estado: {entrevista.get('estado', 'sin estado')})")
    for p in entrevista["perfiles"].values():
        print(f"  {p['nombre']:32} gama {p['gama']:7} {p['ram_gb']:3} GB  GPU: {'sí' if p['gpu'] else 'no'}")
    if parser.parse_args().escribir_doc:
        escribir_perfiles_en_documento()
        print(f"Escrito {RUTA_DOCUMENTO}. Reindexá el RAG: uv run python -m rag.ingest")


if __name__ == "__main__":
    main()
