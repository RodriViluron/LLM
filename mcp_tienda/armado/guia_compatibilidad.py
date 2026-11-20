"""Genera la sección «Números que usa el verificador» de rag/docs/guia_compatibilidad.md.

La guía explica en prosa lo mismo que verifican las reglas de `reglas.py`. Los números (margen de la
fuente, consumo fijo, formato de memoria, sockets, cantidades) y qué reglas son críticas salen del
código, así el documento no queda viejo cuando cambia una regla.

Uso:
    uv run python -m mcp_tienda.armado.guia_compatibilidad                 muestra el bloque
    uv run python -m mcp_tienda.armado.guia_compatibilidad --escribir-doc  lo escribe en el documento
Después de escribir, reindexar el RAG: uv run python -m rag.ingest
"""

import argparse
import math
from pathlib import Path

from mcp_tienda.armado.reglas import CONSUMO_BASE_W, FORMATO_MODULO_PC, MARGEN_FUENTE, REGLAS_AVISO
from mcp_tienda.config import RAIZ
from mcp_tienda.ingesta.extraccion import SOCKETS
from mcp_tienda.modelos import CANTIDAD_MAXIMA

RUTA_DOCUMENTO = RAIZ / "rag" / "docs" / "guia_compatibilidad.md"
MARCA_INICIO = "<!-- GUIA: INICIO (generado desde mcp_tienda/armado/reglas.py: no editar a mano) -->"
MARCA_FIN = "<!-- GUIA: FIN -->"

# Nombre para el usuario de cada regla, en el orden en que se explican.
NOMBRES_REGLAS = {
    "socket_cpu_placa": "socket",
    "generacion_cpu_placa": "generación",
    "tipo_ram": "tipo de memoria",
    "modulo_ram": "formato de memoria",
    "ranuras_ram": "ranuras de memoria",
    "puertos_almacenamiento": "ranuras y puertos de discos",
    "video": "video",
    "cooler": "cooler incluido",
    "socket_cooler": "socket del cooler",
    "potencia_cooler": "potencia del cooler",
    "potencia_fuente": "potencia de la fuente",
    "formato_placa_gabinete": "formato del gabinete",
    "largo_gpu_gabinete": "largo de la placa de video",
    "conectores_gpu": "conectores de energía de la placa de video",
}

# Valores de los ejemplos (no son reglas: solo ilustran la cuenta).
EJEMPLO_CPU_W = 117
EJEMPLO_RECOMENDADA_W = 550


def _lista(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def bloque_de_numeros() -> str:
    sin_gpu = math.ceil((EJEMPLO_CPU_W + CONSUMO_BASE_W) * (1 + MARGEN_FUENTE))
    criticas = [n for r, n in NOMBRES_REGLAS.items() if r not in REGLAS_AVISO]
    avisos = [NOMBRES_REGLAS[r] for r in REGLAS_AVISO]
    lineas = [
        MARCA_INICIO,
        "",
        f"- Margen de la fuente: **{round(MARGEN_FUENTE * 100)} %** por encima del consumo estimado.",
        f"- Consumo fijo del resto de la PC: **{CONSUMO_BASE_W} W** (motherboard, memoria, discos, ventiladores y USB).",
        f"- Ejemplo sin placa de video: procesador de {EJEMPLO_CPU_W} W → ({EJEMPLO_CPU_W} + {CONSUMO_BASE_W}) × "
        f"{1 + MARGEN_FUENTE:.2f}".replace(".", ",") + f" = **{sin_gpu} W** como mínimo.",
        f"- Ejemplo con placa de video que recomienda {EJEMPLO_RECOMENDADA_W} W: hace falta la más alta entre "
        f"{sin_gpu} W y {EJEMPLO_RECOMENDADA_W} W → **{max(sin_gpu, EJEMPLO_RECOMENDADA_W)} W**.",
        f"- Formato de memoria para PC de escritorio: **{FORMATO_MODULO_PC}**.",
        f"- Sockets que se arman: **{_lista(list(SOCKETS))}**.",
        f"- Unidades por lugar: hasta **{CANTIDAD_MAXIMA}** de memoria y de cada disco.",
        f"- Reglas críticas: {_lista(criticas)}.",
        f"- Avisos: {_lista(avisos)}.",
        "",
        MARCA_FIN,
    ]
    return "\n".join(lineas)


def escribir_en_documento(ruta: Path | None = None) -> None:
    """Reemplaza el bloque entre las marcas (el resto del documento se escribe a mano)."""
    ruta = ruta or RUTA_DOCUMENTO
    texto = ruta.read_text(encoding="utf-8")
    if MARCA_INICIO not in texto or MARCA_FIN not in texto:
        raise ValueError(f"{ruta} no tiene las marcas del bloque generado")
    inicio, fin = texto.index(MARCA_INICIO), texto.index(MARCA_FIN) + len(MARCA_FIN)
    ruta.write_text(texto[:inicio] + bloque_de_numeros() + texto[fin:], encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--escribir-doc", action="store_true")
    args = parser.parse_args()
    print(bloque_de_numeros())
    if args.escribir_doc:
        escribir_en_documento()
        print(f"\nEscrito {RUTA_DOCUMENTO}. Reindexá el RAG: uv run python -m rag.ingest")


if __name__ == "__main__":
    main()
