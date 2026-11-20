"""Ubica los requisitos de un juego o programa en una gama, por código (problema 8).

buscar_especificaciones_web trae texto de sitios de requisitos («GTX 1060 or RX 5500 XT», «Intel
i5-8600 or AMD Ryzen 5 3600»). Acá se leen los modelos de CPU y GPU, se separan en mínimos y
recomendados, y cada uno se ubica con la tabla de gamas (gamas.clasificar_gama). La tool agrega el
resultado a su respuesta: el modelo recibe la gama ya calculada y no tiene que encadenar otra tool
(medido: 0 de 5 corridas consultaban el RAG después de buscar en la web).

Cómo se decide la gama:
- Por componente, alcanza con una alternativa: si piden «RTX 2060 Super o RX 5700», la gama del
  requisito de GPU es la más baja entre las alternativas que están en la tabla.
- Por sección (mínimos o recomendados), manda el componente más exigente: la gama más alta entre CPU y GPU.
- La gama sugerida es la de los recomendados; si no hay recomendados, la de los mínimos.
- Si ningún modelo está en la tabla, no hay gama: se dice, no se adivina.

Después, buscar_en_catalogo busca en la tienda esas mismas piezas (regla 13 del prompt): primero
va la CPU o GPU exacta que pide el juego; solo si la tienda no la tiene, otra de la misma gama.
"""

import re
from collections.abc import Callable
from pathlib import Path

from mcp_tienda.armado.gamas import GAMAS, clasificar_gama, mismo_modelo, texto_de_busqueda

SECCIONES = ("minimos", "recomendados")
_MARCA = re.compile(r"m[ií]nim[oa]s?|recomendad[oa]s?|recomiend\w*", re.IGNORECASE)

_SUFIJO_GPU = {"ti": " Ti", "super": " Super", "xt": " XT", "xtx": " XTX"}
_PATRONES = [
    ("gpu", re.compile(r"\b(GTX|RTX|GT)\s?-?(\d{3,4})(?:\s?(Ti|Super))?\b", re.IGNORECASE),
     lambda m: f"{m[1].upper()} {m[2]}{_SUFIJO_GPU.get((m[3] or '').lower(), '')}"),
    ("gpu", re.compile(r"\b(RX)\s?(\d{3,4})(?:\s?(XTX|XT))?\b", re.IGNORECASE),
     lambda m: f"RX {m[2]}{_SUFIJO_GPU.get((m[3] or '').lower(), '')}"),
    ("gpu", re.compile(r"\bArc\s+(A\d{3})\b", re.IGNORECASE), lambda m: f"Arc {m[1].upper()}"),
    ("cpu", re.compile(r"\b(?:Core\s+)?i([3579])[-\s]?(\d{4,5})([A-Z]{0,2})\b", re.IGNORECASE),
     lambda m: f"Core i{m[1]}-{m[2]}{m[3].upper()}"),
    ("cpu", re.compile(r"\bRyzen\s+([3579])\s+(\d{4})([A-Z0-9]{0,3})\b", re.IGNORECASE),
     lambda m: f"Ryzen {m[1]} {m[2]}{m[3].upper()}"),
    ("cpu", re.compile(r"\bUltra\s+([579])\s+(\d{3})([A-Z]{0,2})\b", re.IGNORECASE),
     lambda m: f"Ultra {m[1]} {m[2]}{m[3].upper()}"),
]


def modelos_en_texto(texto: str) -> list[tuple[str, str]]:
    """(componente, modelo) de cada CPU o GPU nombrado en un texto corto, como una consulta al RAG.

    A diferencia de los resultados web, acá no se exige que la línea hable de CPU o GPU.
    """
    encontrados = []
    for componente, patron, formato in _PATRONES:
        encontrados += [(m.start(), componente, formato(m)) for m in patron.finditer(texto)]
    return list(dict.fromkeys((c, m) for _, c, m in sorted(encontrados)))


# Un modelo cuenta como requisito si su línea (o la anterior no vacía) habla de CPU o GPU. Así no entran
# las etiquetas sueltas de los gráficos de benchmark que traen algunos sitios («RTX 3060» sobre una barra).
_CONTEXTO = re.compile(r"procesador|cpu|gpu|gr[aá]fic|tarjeta|video|requisit|requier", re.IGNORECASE)


def _en_contexto_de_requisito(texto: str, posicion: int) -> bool:
    inicio = texto.rfind("\n", 0, posicion) + 1
    fin = texto.find("\n", posicion)
    linea = texto[inicio: fin if fin != -1 else len(texto)]
    anteriores = [renglon for renglon in texto[:inicio].splitlines() if renglon.strip()]
    return bool(_CONTEXTO.search(linea) or (anteriores and _CONTEXTO.search(anteriores[-1])))


def _modelos(texto: str) -> list[tuple[int, str, str]]:
    """(posición, componente, modelo) de cada CPU o GPU que aparece en el texto como requisito."""
    encontrados = []
    for componente, patron, formato in _PATRONES:
        encontrados += [(m.start(), componente, formato(m)) for m in patron.finditer(texto)
                        if _en_contexto_de_requisito(texto, m.start())]
    return sorted(encontrados)


def leer_requisitos(resultados: list[dict]) -> dict:
    """{"minimos": {"cpu": [...], "gpu": [...]}, "recomendados": {...}} a partir de los resultados web.

    Cada aparición vota por la sección de la última marca («mínimos», «recomendados») que tiene antes; sin
    marcas, vota por mínimos. El modelo va a la sección con más votos sumando todos los sitios, y si
    empatan, a recomendados (lo más exigente). Así pesan más los sitios con secciones claras que un
    párrafo suelto («el i5-4670K es lo mínimo, pero apuntá a un i5-8600»).
    """
    votos: dict[tuple[str, str], dict[str, int]] = {}   # (componente, modelo) -> votos por sección
    for resultado in resultados:
        texto = resultado.get("content", "")
        marcas = [(m.start(), "minimos" if m.group().lower().startswith("m") else "recomendados")
                  for m in _MARCA.finditer(texto)]
        for posicion, componente, modelo in _modelos(texto):
            previas = [s for p, s in marcas if p < posicion]
            seccion = previas[-1] if previas else "minimos"
            conteo = votos.setdefault((componente, modelo), {s: 0 for s in SECCIONES})
            conteo[seccion] += 1
    req = {s: {"cpu": [], "gpu": []} for s in SECCIONES}
    for (componente, modelo), conteo in votos.items():   # se conserva el orden de aparición
        seccion = "minimos" if conteo["minimos"] > conteo["recomendados"] else "recomendados"
        req[seccion][componente].append(modelo)
    return req


def _orden(gama: str) -> int:
    return GAMAS.index(gama)


def ubicar_requisitos(req: dict, ruta_tabla: Path | None = None) -> dict:
    """Gama de cada modelo según la tabla, gama de cada sección y gama sugerida."""
    ubicados: dict = {}
    for seccion in SECCIONES:
        datos: dict = {}
        por_componente = []
        for componente in ("cpu", "gpu"):
            datos[componente] = [(m, clasificar_gama(m, componente, ruta_tabla)) for m in req[seccion][componente]]
            gamas = [g for _, g in datos[componente] if g]
            if gamas:
                por_componente.append(min(gamas, key=_orden))   # alcanza con una alternativa
        datos["gama"] = max(por_componente, key=_orden) if por_componente else None   # manda el más exigente
        ubicados[seccion] = datos
    hay_recomendados = any(req["recomendados"][c] for c in ("cpu", "gpu"))
    ubicados["gama_sugerida"] = ubicados["recomendados"]["gama"] if hay_recomendados else ubicados["minimos"]["gama"]
    ubicados["segun"] = "recomendados" if hay_recomendados else "minimos"
    return ubicados


MODELOS_A_BUSCAR = 3   # por componente: los requisitos suelen dar 1 a 3 alternativas («RTX 2060 o RX 5700»)


def buscar_en_catalogo(ubicados: dict, buscar: Callable[[str, str], list[dict]]) -> list[dict]:
    """Busca en la tienda cada CPU y GPU de los requisitos (los recomendados, o los mínimos si no hay).

    `buscar(componente, texto)` devuelve productos con codigo, nombre, precio y stock (en la tool
    es buscar_productos del servidor MCP, solo con stock). De lo que vuelve se quedan solo los que
    son exactamente ese modelo (mismo_modelo). Devuelve una entrada por modelo, con sus productos.
    """
    seccion = ubicados.get(ubicados.get("segun") or "", {})
    encontrados = []
    for componente in ("cpu", "gpu"):
        # Tope: la lista sale de texto de la web; no se hacen más de MODELOS_A_BUSCAR búsquedas por componente.
        for modelo, gama in seccion.get(componente, [])[:MODELOS_A_BUSCAR]:
            productos = [p for p in buscar(componente, texto_de_busqueda(modelo))
                         if mismo_modelo(modelo, p.get("nombre", ""))]
            encontrados.append({"componente": componente, "modelo": modelo, "gama": gama,
                                "productos": productos[:3]})
    return encontrados


def _pesos(valor: float) -> str:
    return f"$ {int(round(valor)):,}".replace(",", ".")


def texto_de_catalogo(encontrados: list[dict]) -> str:
    """Lo que la tool agrega para el modelo: qué piezas exactas de los requisitos tiene la tienda."""
    if not encontrados:
        return ""
    # Es un dato calculado por el código (productos del catálogo propio), no texto de la web. Qué hacer
    # con él lo dice la regla 13 del prompt; acá no van órdenes.
    lineas = ["Catálogo de la tienda para los modelos de los requisitos (búsqueda por código; con varias "
              "alternativas, alcanza con una):"]
    for e in encontrados:
        cabeza = f"- {e['componente'].upper()} {e['modelo']} (gama {e['gama'] or 'sin datos'})"
        if e["productos"]:
            piezas = "; ".join(f"{p['codigo']} «{p['nombre']}» {_pesos(p['precio'])}, stock {p['stock']}"
                               for p in e["productos"])
            lineas.append(f"{cabeza}: disponible en la tienda: {piezas}.")
        elif e["gama"]:
            lineas.append(f"{cabeza}: no está en la tienda con stock. Alternativa: otra de gama {e['gama']} "
                          "(buscar_pieza_armado).")
        else:
            lineas.append(f"{cabeza}: no está en la tienda con stock y no figura en la tabla de gamas.")
    return "\n".join(lineas)


def texto_de_gama(ubicados: dict) -> str:
    """Lo que la tool agrega a su respuesta para el modelo. Vacío si los resultados no nombran CPU ni GPU."""
    modelos = [(m, g) for s in SECCIONES for c in ("cpu", "gpu") for m, g in ubicados[s][c]]
    if not modelos:
        return ""
    titulos = {"minimos": "Mínimos", "recomendados": "Recomendados"}
    lineas = ["Gama según la tabla de referencia (la calculó el código con tabla_cpu_gpu_por_gama.md: "
              "no la adivines ni la cambies):"]
    for seccion in SECCIONES:
        partes = []
        for componente in ("gpu", "cpu"):
            if ubicados[seccion][componente]:
                lista = ", ".join(f"{m} → {g or 'sin datos'}" for m, g in ubicados[seccion][componente])
                partes.append(f"{componente.upper()} {lista}")
        if partes:
            lineas.append(f"- {titulos[seccion]}: {'; '.join(partes)}")
    gama = ubicados["gama_sugerida"]
    if gama:
        lineas.append(f"Gama sugerida: {gama} (por los requisitos {titulos[ubicados['segun']].lower()}). Decíselo "
                      "al usuario y proponé el presupuesto de referencia de esa gama.")
    else:
        faltan = ", ".join(dict.fromkeys(m for m, g in modelos if g is None))
        lineas.append(f"Gama sugerida: sin datos. Estos modelos no están en la tabla de gamas: {faltan}. "
                      "Decíselo al usuario; no la adivines y no preguntes la gama: seguí la entrevista y usá la gama del perfil.")
    return "\n".join(lineas)
