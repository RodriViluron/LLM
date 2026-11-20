"""Entrevista del armado por código (paso 10, problema 26).

Recorre el árbol de `datos/entrevista_armado.yaml` (vía perfiles.cargar_entrevista):
- `siguiente(respuestas)` dice qué pregunta sigue, con sus opciones exactas, o da el perfil final;
- `filtros_del_perfil(lugar, perfil)` convierte el perfil en filtros para buscar cada pieza.

No habla con el usuario ni con el modelo: el que pregunta es el agente, con las opciones que
devuelve esta función. Si una respuesta no es una opción, se rechaza y se devuelven las válidas.
"""

from mcp_tienda.armado.perfiles import cargar_entrevista


class ErrorEntrevista(ValueError):
    """La respuesta no corresponde a la entrevista; el mensaje dice cuáles serían válidas."""


def _por_id(entrevista: dict) -> dict:
    return {p["id"]: p for p in entrevista["preguntas"]}


def _opciones(pregunta: dict) -> dict:
    return pregunta["opciones"]


def _perfil_de(respuestas: dict, entrevista: dict) -> str | None:
    """Clave del perfil que dan las respuestas (la última que lo cambia gana, por ejemplo «Sí» a transmitir)."""
    perfil = None
    for pregunta in entrevista["preguntas"]:
        respuesta = respuestas.get(pregunta["id"])
        if respuesta is not None and "perfil" in _opciones(pregunta)[respuesta]:
            perfil = _opciones(pregunta)[respuesta]["perfil"]
    return perfil


def _siguiente_en_orden(actual: dict, entrevista: dict, perfil: str | None) -> dict | None:
    """La pregunta que sigue a `actual` en el orden del archivo, si corresponde preguntarla."""
    preguntas = entrevista["preguntas"]
    indice = [p["id"] for p in preguntas].index(actual["id"])
    for pregunta in preguntas[indice + 1:]:
        if pregunta.get("solo_si_llega"):
            continue   # solo se llega por un salto («sigue») de otra respuesta
        if "solo_si_perfil" in pregunta and perfil not in pregunta["solo_si_perfil"]:
            continue
        return pregunta
    return None


def _datos_de_perfil(clave: str, respuestas: dict, entrevista: dict) -> dict:
    base = entrevista["perfiles"][clave]
    perfil = {
        "clave": clave, "nombre": base["nombre"], "gama": base["gama"], "ram_gb": base["ram_gb"],
        "gpu": base["gpu"], "pesa_mas": list(base["pesa_mas"]), "disco_gb": None,
        "segundo_disco": False, "placa_escalable": False,
    }
    for pregunta in entrevista["preguntas"]:
        respuesta = respuestas.get(pregunta["id"])
        if respuesta is None:
            continue
        efectos = _opciones(pregunta)[respuesta]
        if "ram_gb_min" in efectos:
            perfil["ram_gb"] = max(perfil["ram_gb"], efectos["ram_gb_min"])
        if "disco_gb_min" in efectos:
            perfil["disco_gb"] = efectos["disco_gb_min"]
        if efectos.get("segundo_disco"):
            perfil["segundo_disco"] = True
        if efectos.get("placa") == "escalable":
            perfil["placa_escalable"] = True
    return perfil


def _pregunta_para_el_modelo(pregunta: dict) -> dict:
    return {"id": pregunta["id"], "pregunta": pregunta["pregunta"], "opciones": list(_opciones(pregunta))}


def siguiente(respuestas: dict[str, str], entrevista: dict | None = None) -> dict:
    """Devuelve {"completa": False, "pregunta": {...}} o {"completa": True, "perfil": {...}}.

    `respuestas` es {id de pregunta: opción tal como figura en el archivo}. Se valida todo: un id
    desconocido, una pregunta que no corresponde al camino o una opción inexistente dan ErrorEntrevista.
    """
    entrevista = entrevista or cargar_entrevista()
    por_id = _por_id(entrevista)
    for id_pregunta in respuestas:
        if id_pregunta not in por_id:
            raise ErrorEntrevista(f"No existe la pregunta «{id_pregunta}». Preguntas: {', '.join(por_id)}")

    camino: list[str] = []
    actual = entrevista["preguntas"][0]
    while True:
        if actual["id"] not in respuestas:
            if respuestas.keys() - set(camino) - {actual["id"]}:
                sobrantes = ", ".join(sorted(respuestas.keys() - set(camino)))
                raise ErrorEntrevista(f"Esas respuestas no corresponden al camino actual: {sobrantes}")
            return {"completa": False, "pregunta": _pregunta_para_el_modelo(actual)}
        respuesta = respuestas[actual["id"]]
        if respuesta not in _opciones(actual):
            raise ErrorEntrevista(f"«{respuesta}» no es una opción de «{actual['pregunta']}». "
                                  f"Opciones: {' | '.join(_opciones(actual))}")
        camino.append(actual["id"])
        efectos = _opciones(actual)[respuesta]
        if "sigue" in efectos:
            actual = por_id[efectos["sigue"]]
            continue
        perfil = _perfil_de({k: respuestas[k] for k in camino}, entrevista)
        proxima = _siguiente_en_orden(actual, entrevista, perfil)
        if proxima is None:
            if respuestas.keys() - set(camino):
                sobrantes = ", ".join(sorted(respuestas.keys() - set(camino)))
                raise ErrorEntrevista(f"Esas respuestas no corresponden al camino actual: {sobrantes}")
            return {"completa": True, "perfil": _datos_de_perfil(perfil, respuestas, entrevista)}
        actual = proxima


UNIDADES_MAX_RAM = 2   # la memoria del perfil se cubre con hasta 2 productos iguales (2 módulos o 2 kits)


def cantidad_de_ram(perfil: dict, capacidad_gb: int | None) -> int | None:
    """Cuántas unidades de un producto de RAM hacen falta para la memoria del perfil.

    `capacidad_gb` es el total del producto (un kit 2x16 trae 32). None si no hay dato o si hacen
    falta más de UNIDADES_MAX_RAM unidades. Si entran en la placa lo decide verificar_compatibilidad.
    """
    if not capacidad_gb:
        return None
    cantidad = -(-perfil["ram_gb"] // capacidad_gb)   # división redondeando hacia arriba
    return cantidad if cantidad <= UNIDADES_MAX_RAM else None


def filtros_del_perfil(lugar: str, perfil: dict) -> dict:
    """Filtros para buscar la pieza de `lugar` según el perfil.

    Devuelve {"atributos": {...}} y, si el perfil fija una gama, también "gama" (cpu y gpu la tienen
    en la tabla de gamas). Solo filtra lo que la entrevista pide; el resto lo decide el armado.
    La RAM se filtra por lo que trae cada producto: la memoria del perfil dividida en hasta
    UNIDADES_MAX_RAM unidades (con 64 GB se buscan productos de 32 GB o más).
    """
    filtros: dict = {"atributos": {}}
    if lugar in ("cpu", "gpu"):
        filtros["gama"] = perfil["gama"]
    elif lugar == "ram":
        filtros["atributos"]["capacidad_gb__min"] = -(-perfil["ram_gb"] // UNIDADES_MAX_RAM)
    elif lugar == "motherboard" and perfil["placa_escalable"]:
        filtros["atributos"].update({"ranuras_ram__min": 4, "ranuras_m2__min": 2})
    elif lugar == "almacenamiento_extra" and perfil["segundo_disco"] and perfil["disco_gb"]:
        filtros["atributos"]["capacidad_gb__min"] = perfil["disco_gb"]
    return filtros


def piezas_faltantes(perfil: dict | None, configuracion: dict | None) -> list[dict]:
    """Qué lugares faltan o quedan cortos respecto al perfil y a lo elegido (sin asumir datos faltantes).

    Devuelve [{"lugar": ..., "motivo": ...}] en orden lógico de armado.
    """
    componentes = (configuracion or {}).get("componentes") or {}
    cantidades = (configuracion or {}).get("cantidades") or {}
    nombre_perfil = (perfil or {}).get("nombre") or (perfil or {}).get("clave") or "elegido"
    faltan: list[dict] = []

    if "cpu" not in componentes:
        faltan.append({"lugar": "cpu", "motivo": "falta el procesador (cpu)"})
    elif componentes["cpu"].get("atributos", {}).get("incluye_cooler") == "no" and "cooler" not in componentes:
        faltan.append({"lugar": "cooler", "motivo": "falta el cooler: el procesador elegido no trae cooler"})

    if "motherboard" not in componentes:
        faltan.append({"lugar": "motherboard", "motivo": "falta la placa madre (motherboard)"})

    ram_min = (perfil or {}).get("ram_gb")
    if "ram" not in componentes:
        detalle = f" (el perfil {nombre_perfil} pide al menos {ram_min} GB)" if ram_min else ""
        faltan.append({"lugar": "ram", "motivo": f"falta la memoria RAM (ram){detalle}"})
    elif ram_min:
        capacidad = componentes["ram"].get("atributos", {}).get("capacidad_gb")
        unidades = cantidades.get("ram", 1)
        if capacidad is None:
            faltan.append({
                "lugar": "ram",
                "motivo": f"la memoria RAM elegida no informa su capacidad en GB (el perfil {nombre_perfil} pide al menos {ram_min} GB)",
            })
        elif capacidad * unidades < ram_min:
            faltan.append({
                "lugar": "ram",
                "motivo": (f"RAM insuficiente: hay {capacidad * unidades} GB ({unidades} × {capacidad} GB) "
                           f"y el perfil {nombre_perfil} pide al menos {ram_min} GB"),
            })

    if "almacenamiento" not in componentes:
        faltan.append({"lugar": "almacenamiento", "motivo": "falta el disco principal (almacenamiento)"})

    if perfil and perfil.get("segundo_disco") and "almacenamiento_extra" not in componentes:
        min_disco = f" de al menos {perfil['disco_gb']} GB" if perfil.get("disco_gb") else ""
        faltan.append({
            "lugar": "almacenamiento_extra",
            "motivo": f"falta el segundo disco (almacenamiento_extra{min_disco}): el perfil {nombre_perfil} lo pide",
        })

    if "gpu" not in componentes:
        if perfil and perfil.get("gpu"):
            faltan.append({
                "lugar": "gpu",
                "motivo": f"falta la GPU dedicada (gpu): el perfil {nombre_perfil} la pide",
            })
        elif "cpu" in componentes:
            video = componentes["cpu"].get("atributos", {}).get("video_integrado")
            if video == "no":
                faltan.append({
                    "lugar": "gpu",
                    "motivo": "falta la GPU dedicada (gpu): el procesador elegido no tiene gráficos integrados",
                })
            elif video is None:
                # Sin datos no hay afirmación: se avisa, pero no cuenta como pieza que falta (el reintento
                # de armado_completo no puede resolverlo y buscar_pieza_armado no busca GPU sin motivo).
                faltan.append({
                    "lugar": "gpu", "sin_datos": True,
                    "motivo": "sin datos de gráficos integrados en el procesador elegido: no se sabe si hace falta gpu",
                })

    if "gabinete" not in componentes:
        faltan.append({"lugar": "gabinete", "motivo": "falta el gabinete (gabinete)"})

    incluye_fuente = componentes.get("gabinete", {}).get("atributos", {}).get("incluye_fuente") == "si"
    if not incluye_fuente and "fuente" not in componentes:
        faltan.append({"lugar": "fuente", "motivo": "falta la fuente de alimentación (fuente)"})

    return faltan


def texto_piezas_faltantes(faltantes: list[dict]) -> str:
    """Resumen en una oración calculado por código (solo dato, sin órdenes)."""
    faltan = [f for f in faltantes if not f.get("sin_datos")]
    avisos = [f for f in faltantes if f.get("sin_datos")]
    texto = ("Faltan: " + "; ".join(f["motivo"] for f in faltan) + ".") if faltan else "Armado completo según el perfil."
    if avisos:
        texto += " Aviso: " + "; ".join(f["motivo"] for f in avisos) + "."
    return texto


def faltan_de_verdad(faltantes: list[dict]) -> list[dict]:
    """Las piezas que faltan, sin los avisos de «sin datos» (esos se informan, no se fuerzan)."""
    return [f for f in faltantes if not f.get("sin_datos")]


# --- Lo que el usuario ya dijo en su pedido (paso 15) --------------------------------------------
#
# «Armame una PC para jugar Wukong en 1440p» ya contesta el uso y la pantalla: no se vuelve a
# preguntar. Las respuestas se leen por código con expresiones regulares (como montos.py) y solo
# se aceptan las que caen en el camino de la entrevista; lo que no se entiende, se pregunta.

import re  # noqa: E402

from mcp_tienda.armado.gamas import GAMAS  # noqa: E402

_PISTAS = {
    "uso": [
        (r"\b(jug\w*|juego\w*|gam(er|ing|ear)|gamea\w*)\b", "Jugar"),
        (r"\b(edit\w*\s+(de\s+)?videos?|edici[oó]n\s+de\s+videos?|premiere|davinci|after\s+effects)\b",
         "Diseño o edición de video"),
        (r"\b(dise[nñ]\w*|photoshop|autocad|illustrator|revit|solidworks|blender)\b", "Diseño o edición de video"),
        (r"\b(program\w*|desarroll\w*|codear|codigo|código)\b", "Programar"),
        (r"\b(oficina|estudi\w*|facultad|escuela|colegio|planillas?|excel|word|mails?|navegar)\b",
         "Oficina o estudio"),
    ],
    "monitor": [
        (r"\b(1080p?|full\s?hd|fhd)\b", "Un monitor común (1080p)"),
        (r"\b(1440p?|2k|qhd)\b", "Un monitor 2K (1440p)"),
        (r"\b(4k|2160p?|uhd|televisor|tele|tv)\b", "Un televisor o monitor 4K"),
    ],
    "tipo_de_trabajo": [
        (r"\b(edit\w*\s+(de\s+)?videos?|edici[oó]n\s+de\s+videos?|premiere|davinci|after\s+effects)\b",
         "Edición de video"),
        (r"\b(dise[nñ]\w*|photoshop|autocad|illustrator|revit|solidworks)\b", "Diseño (Photoshop, AutoCAD)"),
    ],
    "transmitir": [(r"\b(stream\w*|transmit\w*|twitch|youtube)\b", "Sí")],
    "multitarea": [(r"\b(muchos\s+programas|muchas\s+pesta[nñ]as|multitarea)\b", "Sí, muchos")],
    "archivos": [(r"\b(muchos\s+(videos|fotos|juegos|archivos)|mucho\s+espacio|disco\s+grande|otro\s+grande|"
                  r"segundo\s+disco|dos\s+discos)\b", "Sí, muchos")],
    "mejora": [(r"\b(mejorarla|ampliarla|actualizarla|escalable)\b|\bmejorar\w*\s+m[aá]s\s+adelante\b", "Sí")],
}


def _respuesta_en_texto(id_pregunta: str, texto: str) -> str | None:
    """La opción que el texto contesta para esa pregunta; None si no dice nada o dice dos cosas."""
    encontradas = {opcion for patron, opcion in _PISTAS.get(id_pregunta, ())
                   if re.search(patron, texto, re.IGNORECASE)}
    return encontradas.pop() if len(encontradas) == 1 else None


def pistas_del_mensaje(texto: str) -> dict[str, str]:
    """{id de pregunta: opción} de todo lo que el texto contesta, esté o no en el camino todavía."""
    return {id_pregunta: opcion for id_pregunta in _PISTAS
            if (opcion := _respuesta_en_texto(id_pregunta, texto)) is not None}


def completar_con_pistas(respuestas: dict[str, str], pistas: dict[str, str],
                         entrevista: dict | None = None) -> dict[str, str]:
    """Agrega las pistas a medida que la entrevista llega a cada pregunta; para en la primera sin pista.

    Se avanza con `siguiente`, así nunca queda una respuesta fuera del camino. Se llama cada vez que
    el usuario contesta, porque una pista de más adelante («otro disco grande») recién sirve cuando la
    entrevista llega a esa pregunta.
    """
    entrevista = entrevista or cargar_entrevista()
    respuestas = dict(respuestas)
    while True:
        resultado = siguiente(respuestas, entrevista)
        if resultado["completa"]:
            return respuestas
        pregunta = resultado["pregunta"]
        opcion = pistas.get(pregunta["id"])
        if opcion is None or opcion not in pregunta["opciones"]:
            return respuestas
        respuestas[pregunta["id"]] = opcion


def respuestas_del_mensaje(texto: str, entrevista: dict | None = None) -> dict[str, str]:
    """Respuestas que el pedido ya contesta, en el orden del camino (hasta la primera que falta)."""
    return completar_con_pistas({}, pistas_del_mensaje(texto), entrevista)


# Palabras que pueden seguir a «jugar» sin ser el nombre de un juego («jugar online», «jugar en 4K»).
_NO_SON_JUEGOS = {
    "a", "al", "el", "la", "los", "las", "un", "una", "en", "con", "de", "y", "o", "que", "juegos", "jueguitos",
    "online", "competitivo", "tranqui", "bien", "algo", "cosas", "todo", "varios", "mucho", "poco", "más", "mas",
    "lo", "tipo", "como", "porque", "pero", "también", "tambien", "sin", "ni", "me", "nos", "y/o", "1080p",
    "1440p", "4k", "2k", "hd", "full", "fullhd", "alto", "alta", "bajo", "baja", "medio", "media", "calidad",
}
_PROGRAMAS = re.compile(r"\b(photoshop|autocad|illustrator|premiere|davinci|after\s+effects|blender|revit|"
                        r"solidworks|sketchup|unreal|unity|lightroom|3ds\s+max|maya|cinema\s+4d)\b", re.IGNORECASE)


def nombra_juego_o_programa(texto: str) -> bool:
    """True si el pedido nombra un juego o programa concreto («jugar al Wukong», «para AutoCAD»).

    En ese caso conviene buscar primero sus requisitos (regla 13) y recién después entrevistar.
    """
    if _PROGRAMAS.search(texto):
        return True
    for m in re.finditer(r"\bjug(?:ar|ando)\s+((?:\w+\s+){0,2}\w+)", texto, re.IGNORECASE):
        palabras = [p.lower() for p in m.group(1).split()]
        if any(p not in _NO_SON_JUEGOS and not p.isdigit() for p in palabras):
            return True
    return False


def con_gama_de_requisitos(perfil: dict, gama_sugerida: str | None) -> dict:
    """Si los requisitos del juego piden una gama más alta que el perfil, manda la de los requisitos."""
    if gama_sugerida not in GAMAS or GAMAS.index(gama_sugerida) <= GAMAS.index(perfil["gama"]):
        return perfil
    return {**perfil, "gama": gama_sugerida, "gama_por_requisitos": True}
