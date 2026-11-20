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
