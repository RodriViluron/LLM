"""Búsqueda en la documentación propia: lo que usa consultar_caracteristicas (problema 5).

Los embeddings quedan para el texto libre. Lo que el código puede decidir, lo decide el código:
- D. Si la consulta nombra un CPU o una GPU («RTX 5060», «Ryzen 5 5600»), la primera respuesta es su
  fila de la tabla de gamas, buscada por código (clasificar_gama), no por parecido de vectores.
- C. Si la consulta nombra una sola gama («qué disco usa la gama alta»), se busca solo en los
  fragmentos de esa gama; si faltan, se completa con los generales. Así no vuelven fragmentos de
  otra gama. Si la base es vieja (sin la metadata `gama`), se busca sin filtro.
"""

import re
from pathlib import Path

from mcp_tienda.armado.gamas import GAMAS, clasificar_gama
from mcp_tienda.armado.requisitos import modelos_en_texto
from rag.ingest import GAMA_GENERAL

FUENTE_TABLA = "tabla_cpu_gpu_por_gama.md"
FUENTE_GAMAS = "gamas.md"
FUENTE_REPARTO = "reparto_presupuesto.md"

_INTENCION_REPARTO = re.compile(
    r"\b(cu[aá]nto\s+(cuesta|sale|vale|gastar)|porcentaje|reparto|presupuesto)\b",
    re.IGNORECASE,
)
_INTENCION_COMPONENTE_GAMA = re.compile(
    r"\b(qu[eé]\s+(procesador|disco|fuente|cooler|placa|ram|memoria)|cu[aá]nt[ao]\s+(ram|memoria)|"
    r"lleva\s+placa\s+de\s+video)\b",
    re.IGNORECASE,
)


def _ordenar_por_intencion(fragmentos: list[dict], consulta: str, gama: str | None) -> list[dict]:
    """Desempate estable entre los fragmentos ya recuperados según la intención de la consulta (problema 29)."""
    if _INTENCION_REPARTO.search(consulta):
        objetivo = FUENTE_REPARTO
    elif gama is not None and _INTENCION_COMPONENTE_GAMA.search(consulta):
        objetivo = FUENTE_GAMAS
    else:
        return fragmentos
    preferidos = [f for f in fragmentos if f["fuente"] == objetivo]
    if not preferidos:
        return fragmentos
    return preferidos + [f for f in fragmentos if f["fuente"] != objetivo]


def gama_de_la_consulta(consulta: str) -> str | None:
    """La gama que nombra la consulta («gama alta», «PC premium»); None si no nombra ninguna o nombra varias."""
    texto = consulta.lower()
    nombradas = {g for g in GAMAS if re.search(rf"\bgama {g}\b", texto)}
    if re.search(r"\bpremium\b", texto):
        nombradas.add("premium")
    return nombradas.pop() if len(nombradas) == 1 else None


def _exactas(consulta: str, ruta_tabla: Path | None) -> list[dict]:
    fragmentos = []
    for componente, modelo in modelos_en_texto(consulta):
        gama = clasificar_gama(modelo, componente, ruta_tabla)
        texto = ("Búsqueda exacta en la tabla de referencia (la hizo el código):\n"
                 "| componente | modelo | gama |\n|---|---|---|\n"
                 f"| {componente} | {modelo} | {gama or 'sin datos'} |")
        if gama is None:
            texto += "\nEse modelo no está en la tabla: no se sabe su gama. No la adivines."
        fragmentos.append({"fuente": FUENTE_TABLA, "texto": texto, "gama": gama or GAMA_GENERAL, "exacta": True})
    return fragmentos


def _a_fragmento(chunk) -> dict:
    return {"fuente": chunk.metadata["source"], "texto": chunk.page_content,
            "gama": chunk.metadata.get("gama", GAMA_GENERAL), "exacta": False}


def buscar_en_documentacion(store, consulta: str, k: int = 4, ruta_tabla: Path | None = None,
                            texto_busqueda: str | None = None) -> list[dict]:
    """Fragmentos para la consulta: primero las filas exactas de la tabla (si nombra modelos), después hasta
    `k` fragmentos por parecido, filtrados por la gama de la consulta si nombra una.

    `texto_busqueda` permite buscar por vectores con otro texto (por ejemplo, un documento hipotético
    en el experimento HyDE) manteniendo el filtro de gama y la tabla exacta sobre `consulta`.
    Cada fragmento: {fuente, texto, gama, exacta}.
    """
    consulta_vector = texto_busqueda or consulta
    exactas = _exactas(consulta, ruta_tabla)
    gama = gama_de_la_consulta(consulta)
    if gama is None:
        chunks = store.similarity_search(consulta_vector, k=k)
    else:
        chunks = store.similarity_search(consulta_vector, k=k, filter={"gama": gama})
        if len(chunks) < k:
            chunks += store.similarity_search(consulta_vector, k=k - len(chunks), filter={"gama": GAMA_GENERAL})
        if not chunks:   # base indexada antes de este cambio: no tiene la metadata `gama`
            chunks = store.similarity_search(consulta_vector, k=k)
    return exactas + _ordenar_por_intencion([_a_fragmento(c) for c in chunks], consulta, gama)
