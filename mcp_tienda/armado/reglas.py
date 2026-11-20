"""Reglas de compatibilidad deterministas (sin LLM).

Cada regla devuelve cumple / no_cumple / sin_datos con un detalle legible. Nunca asume:
si falta un atributo, la respuesta es «sin datos» y el agente se lo tiene que decir al usuario.

Cada resultado dice además si la regla es **crítica**:
- crítica: si da «sin datos», no se puede confirmar el pedido (no se sabe si la PC funciona);
- no crítica: es un aviso. Hoy son el largo de la placa de video y sus conectores de energía,
  que el catálogo real casi nunca informa.
Un «no cumple» bloquea siempre, sea crítica o no.

Piezas obligatorias: cpu, motherboard, ram, almacenamiento y gabinete siempre. La fuente, salvo que
el gabinete traiga una. La placa de video, si la CPU no tiene video integrado. El cooler, si la CPU
no lo trae (ver `lugares_obligatorios`). Si falta elegir una pieza obligatoria, la regla que la
necesita da «sin datos: Falta elegir…». Las reglas de piezas opcionales (largo de la GPU, socket
del cooler) solo se evalúan cuando la pieza está elegida.
"""

import re

from mcp_tienda.modelos import SLOTS, Configuracion, ReporteCompatibilidad, ResultadoRegla

MARGEN_FUENTE = 0.30  # la fuente tiene que dar un 30 % más que el consumo estimado
CONSUMO_BASE_W = 75   # placa madre, RAM, discos, ventiladores y USB, estimado
FORMATO_MODULO_PC = "DIMM"   # SODIMM es de notebook y ECC de servidor: no van en una PC de escritorio

LUGARES_SIEMPRE = ("cpu", "motherboard", "ram", "almacenamiento", "gabinete")
REGLAS_AVISO = ("largo_gpu_gabinete", "conectores_gpu")   # no críticas: «sin datos» no impide confirmar


# --- Ayudas ---------------------------------------------------------------------------

def _resultado(regla: str, estado: str, detalle: str, critica: bool = True) -> ResultadoRegla:
    return ResultadoRegla(regla=regla, estado=estado, detalle=detalle, critica=critica)


def _falta_pieza(regla: str, config: Configuracion, *slots: str, critica: bool = True) -> ResultadoRegla | None:
    faltan = [s for s in slots if s not in config.componentes]
    if faltan:
        return _resultado(regla, "sin_datos", f"Falta elegir: {', '.join(faltan)}", critica)
    return None


def _falta_atributo(regla: str, faltantes: list[tuple[str, str]], config: Configuracion,
                    critica: bool = True) -> ResultadoRegla | None:
    if faltantes:
        partes = [f"{config.componentes[slot].codigo} no informa '{attr}'" for slot, attr in faltantes]
        return _resultado(regla, "sin_datos", "; ".join(partes), critica)
    return None


def _atributos(config: Configuracion, *pedidos: tuple[str, str]):
    valores, faltantes = [], []
    for slot, attr in pedidos:
        valor = config.componentes[slot].atributos.get(attr)
        valores.append(valor)
        if valor is None:
            faltantes.append((slot, attr))
    return valores, faltantes


def consumo_cpu(atributos: dict) -> int | None:
    """Consumo máximo de la CPU. Si el catálogo trae un solo dato, consumo máximo y TDP son iguales."""
    return atributos.get("consumo_max_w") if atributos.get("consumo_max_w") is not None else atributos.get("tdp_w")


def lugares_obligatorios(atributos_por_lugar: dict[str, dict]) -> list[str]:
    """Lugares que tiene que tener el armado, según lo que ya está elegido.

    Recibe {lugar: atributos} de las piezas elegidas. La usan las reglas, Confirmar y el resumen
    que lee el modelo, para que los tres digan lo mismo.
    """
    cpu = atributos_por_lugar.get("cpu", {})
    gabinete = atributos_por_lugar.get("gabinete", {})
    lugares = set(LUGARES_SIEMPRE)
    if gabinete.get("incluye_fuente") != "si":
        lugares.add("fuente")
    if cpu.get("video_integrado") == "no":
        lugares.add("gpu")
    if cpu.get("incluye_cooler") == "no":
        lugares.add("cooler")
    return [s for s in SLOTS if s in lugares]   # en el orden de siempre de los lugares


# --- Procesador y placa ---------------------------------------------------------------

def regla_socket_cpu_placa(config: Configuracion) -> ResultadoRegla:
    regla = "socket_cpu_placa"
    if r := _falta_pieza(regla, config, "cpu", "motherboard"):
        return r
    (s_cpu, s_placa), faltantes = _atributos(config, ("cpu", "socket"), ("motherboard", "socket"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if s_cpu == s_placa:
        return _resultado(regla, "cumple", f"CPU y placa usan {s_cpu}")
    return _resultado(regla, "no_cumple", f"La CPU es {s_cpu} y la placa es {s_placa}")


def regla_generacion_cpu_placa(config: Configuracion) -> ResultadoRegla:
    """Mismo socket no alcanza: una placa puede no soportar una generación más nueva (o necesitar otro BIOS)."""
    regla = "generacion_cpu_placa"
    if r := _falta_pieza(regla, config, "cpu", "motherboard"):
        return r
    (generacion, generaciones), faltantes = _atributos(
        config, ("cpu", "generacion"), ("motherboard", "generaciones"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if generacion in generaciones:
        return _resultado(regla, "cumple", f"La placa soporta la generación {generacion} de la CPU")
    return _resultado(regla, "no_cumple", f"La CPU es de generación {generacion} y la placa soporta las "
                                          f"generaciones {', '.join(generaciones)}")


def regla_video(config: Configuracion) -> ResultadoRegla:
    regla = "video"
    if r := _falta_pieza(regla, config, "cpu"):
        return r
    if "gpu" in config.componentes:
        return _resultado(regla, "cumple", "Tiene placa de video")
    (integrado,), faltantes = _atributos(config, ("cpu", "video_integrado"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if integrado == "si":
        return _resultado(regla, "cumple", "Sin placa de video: usa el video integrado de la CPU")
    return _resultado(regla, "sin_datos", "Falta elegir: gpu (la CPU no tiene video integrado)")


# --- Memoria --------------------------------------------------------------------------

def regla_tipo_ram(config: Configuracion) -> ResultadoRegla:
    regla = "tipo_ram"
    if r := _falta_pieza(regla, config, "ram", "motherboard"):
        return r
    (t_ram, t_placa), faltantes = _atributos(config, ("ram", "tipo"), ("motherboard", "tipo_ram"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if t_ram == t_placa:
        return _resultado(regla, "cumple", f"RAM y placa usan {t_ram}")
    return _resultado(regla, "no_cumple", f"La RAM es {t_ram} y la placa admite {t_placa}")


def regla_modulo_ram(config: Configuracion) -> ResultadoRegla:
    regla = "modulo_ram"
    if r := _falta_pieza(regla, config, "ram"):
        return r
    (formato,), faltantes = _atributos(config, ("ram", "formato_modulo"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if formato == FORMATO_MODULO_PC:
        return _resultado(regla, "cumple", "La RAM es DIMM, de PC de escritorio")
    uso = {"SODIMM": "de notebook", "ECC": "de servidor"}.get(formato, "que no es de PC de escritorio")
    return _resultado(regla, "no_cumple", f"La RAM es {formato} ({uso}): la placa de una PC usa DIMM")


def regla_ranuras_ram(config: Configuracion) -> ResultadoRegla:
    """Cada módulo ocupa una ranura: un kit 2x8GB son 2 módulos; dos kits, 4."""
    regla = "ranuras_ram"
    if r := _falta_pieza(regla, config, "ram", "motherboard"):
        return r
    (modulos, ranuras), faltantes = _atributos(config, ("ram", "modulos"), ("motherboard", "ranuras_ram"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    usados = modulos * config.cantidad("ram")
    detalle = f"{usados} módulos de RAM y la placa tiene {ranuras} ranuras"
    return _resultado(regla, "cumple" if usados <= ranuras else "no_cumple", detalle)


# --- Almacenamiento -------------------------------------------------------------------

LUGARES_DE_DISCO = ("almacenamiento", "almacenamiento_extra")


def regla_puertos_almacenamiento(config: Configuracion) -> ResultadoRegla:
    """Discos M.2 contra ranuras M.2 de la placa, y discos SATA contra puertos SATA.

    Un disco «M.2 SATA» da «sin datos»: va en una ranura M.2, pero no todas las ranuras M.2 lo
    admiten, y el catálogo no dice cuáles.
    """
    regla = "puertos_almacenamiento"
    if r := _falta_pieza(regla, config, "almacenamiento", "motherboard"):
        return r
    placa = config.componentes["motherboard"]
    pedidos, faltantes = {"M.2": 0, "SATA": 0}, []
    for lugar in LUGARES_DE_DISCO:
        if lugar not in config.componentes:
            continue
        disco = config.componentes[lugar]
        if disco.atributos.get("tipo") == "M.2 SATA":
            return _resultado(regla, "sin_datos", f"{disco.codigo} es M.2 SATA: no se sabe si las ranuras M.2 "
                                                  "de la placa lo admiten")
        conexion = disco.atributos.get("conexion")
        if conexion is None:
            faltantes.append((lugar, "conexion"))
            continue
        pedidos[conexion] += config.cantidad(lugar)
    disponibles = {"M.2": placa.atributos.get("ranuras_m2"), "SATA": placa.atributos.get("puertos_sata")}
    for conexion, nombre in (("M.2", "ranuras_m2"), ("SATA", "puertos_sata")):
        if pedidos[conexion] and disponibles[conexion] is None:
            faltantes.append(("motherboard", nombre))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    partes = [f"{pedidos[c]} disco(s) {c} y la placa tiene {disponibles[c]}" for c in ("M.2", "SATA") if pedidos[c]]
    sobran = all(pedidos[c] <= (disponibles[c] or 0) for c in ("M.2", "SATA"))
    return _resultado(regla, "cumple" if sobran else "no_cumple", "; ".join(partes))


# --- Refrigeración --------------------------------------------------------------------

def regla_cooler(config: Configuracion) -> ResultadoRegla:
    regla = "cooler"
    if r := _falta_pieza(regla, config, "cpu"):
        return r
    if "cooler" in config.componentes:
        return _resultado(regla, "cumple", "Tiene cooler elegido")
    (incluye,), faltantes = _atributos(config, ("cpu", "incluye_cooler"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if incluye == "si":
        return _resultado(regla, "cumple", "La CPU trae su cooler")
    return _resultado(regla, "sin_datos", "Falta elegir: cooler (la CPU no trae)")


def regla_socket_cooler(config: Configuracion) -> ResultadoRegla:
    regla = "socket_cooler"
    if r := _falta_pieza(regla, config, "cpu"):
        return r
    (socket, sockets_cooler), faltantes = _atributos(config, ("cpu", "socket"), ("cooler", "sockets"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if socket in sockets_cooler:
        return _resultado(regla, "cumple", f"El cooler soporta {socket}")
    return _resultado(regla, "no_cumple", f"La CPU es {socket} y el cooler soporta {', '.join(sockets_cooler)}")


def regla_potencia_cooler(config: Configuracion) -> ResultadoRegla:
    regla = "potencia_cooler"
    if r := _falta_pieza(regla, config, "cpu"):
        return r
    consumo = consumo_cpu(config.componentes["cpu"].atributos)
    disipa = config.componentes["cooler"].atributos.get("potencia_enfriamiento_w")
    faltantes = ([("cpu", "consumo_max_w")] if consumo is None else []) + \
                ([("cooler", "potencia_enfriamiento_w")] if disipa is None else [])
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if disipa >= consumo:
        return _resultado(regla, "cumple", f"El cooler disipa {disipa} W y la CPU consume hasta {consumo} W")
    return _resultado(regla, "no_cumple", f"El cooler disipa {disipa} W y la CPU consume hasta {consumo} W")


# --- Energía --------------------------------------------------------------------------

def fuente_del_armado(config: Configuracion) -> tuple[str, int | None] | None:
    """(de dónde sale, potencia) de la fuente: la elegida o la que trae el gabinete. None si no hay."""
    if "fuente" in config.componentes:
        return "fuente", config.componentes["fuente"].atributos.get("potencia_w")
    gabinete = config.componentes.get("gabinete")
    if gabinete and gabinete.atributos.get("incluye_fuente") == "si":
        return "gabinete", gabinete.atributos.get("potencia_fuente_w")
    return None


def potencia_requerida(config: Configuracion, margen: float = MARGEN_FUENTE,
                       consumo_base_w: int = CONSUMO_BASE_W) -> tuple[float | None, str, list[tuple[str, str]]]:
    """Watts que tiene que dar la fuente: (requerido, explicación, datos que faltan).

    - Sin placa de video: (consumo de la CPU + resto) con margen.
    - Con placa de video: lo más exigente entre esa cuenta con el consumo de la GPU (si se conoce)
      y la fuente que recomienda el fabricante de la GPU (si la informa). Si no se conoce ninguno de
      los dos datos de la GPU, no se puede calcular.
    """
    cpu = consumo_cpu(config.componentes["cpu"].atributos)
    if cpu is None:
        return None, "", [("cpu", "consumo_max_w")]
    gpu = config.componentes.get("gpu")
    consumo_gpu = gpu.atributos.get("consumo_w") if gpu else 0
    recomendada = gpu.atributos.get("fuente_recomendada_w") if gpu else None
    if gpu and consumo_gpu is None and recomendada is None:
        return None, "", [("gpu", "fuente_recomendada_w"), ("gpu", "consumo_w")]
    opciones = []
    consumo = cpu + (consumo_gpu or 0) + consumo_base_w
    texto_gpu = consumo_gpu if consumo_gpu is not None else "sin dato"
    opciones.append((consumo * (1 + margen),
                     f"consumo estimado {consumo} W (CPU {cpu} + GPU {texto_gpu} + resto {consumo_base_w}) "
                     f"con margen del {margen:.0%}"))
    if recomendada is not None:
        opciones.append((recomendada, f"el fabricante de la placa de video recomienda {recomendada} W"))
    requerido, explicacion = max(opciones, key=lambda o: o[0])
    return requerido, explicacion, []


def regla_potencia_fuente(config: Configuracion, margen: float = MARGEN_FUENTE,
                          consumo_base_w: int = CONSUMO_BASE_W) -> ResultadoRegla:
    regla = "potencia_fuente"
    if r := _falta_pieza(regla, config, "cpu"):
        return r
    fuente = fuente_del_armado(config)
    if fuente is None:
        return _resultado(regla, "sin_datos", "Falta elegir: fuente (el gabinete no trae)")
    origen, potencia = fuente
    requerido, explicacion, faltantes = potencia_requerida(config, margen, consumo_base_w)
    if potencia is None:
        faltantes.append((origen, "potencia_w" if origen == "fuente" else "potencia_fuente_w"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    de_donde = "la fuente" if origen == "fuente" else "la fuente que trae el gabinete"
    detalle = f"Hacen falta {requerido:.0f} W ({explicacion}) y {de_donde} da {potencia} W"
    return _resultado(regla, "cumple" if potencia >= requerido else "no_cumple", detalle)


_CONECTOR = re.compile(r"(\d+)\s*x\s*(6|8|16)\s*pin", re.IGNORECASE)


def regla_conectores_gpu(config: Configuracion) -> ResultadoRegla:
    """Conectores PCIe de 6 u 8 pines que pide la placa de video contra los que tiene la fuente. No crítica."""
    regla = "conectores_gpu"
    if "fuente" not in config.componentes:
        return _resultado(regla, "sin_datos", "La fuente del gabinete no informa sus conectores", critica=False)
    (pide, tiene), faltantes = _atributos(config, ("gpu", "conectores_energia"), ("fuente", "conectores_pcie"))
    if r := _falta_atributo(regla, faltantes, config, critica=False):
        return r
    partes = _CONECTOR.findall(pide)
    if not partes or any(pines == "16" for _, pines in partes):
        return _resultado(regla, "sin_datos", f"La placa de video pide {pide}: no se puede contar con los "
                                              "conectores PCIe que informa la fuente", critica=False)
    necesarios = sum(int(n) for n, _ in partes)
    estado = "cumple" if tiene >= necesarios else "no_cumple"
    return _resultado(regla, estado, f"La placa de video pide {pide} y la fuente tiene {tiene} conectores PCIe",
                      critica=False)


# --- Gabinete -------------------------------------------------------------------------

def regla_formato_placa_gabinete(config: Configuracion) -> ResultadoRegla:
    regla = "formato_placa_gabinete"
    if r := _falta_pieza(regla, config, "motherboard", "gabinete"):
        return r
    (formato, admitidos), faltantes = _atributos(
        config, ("motherboard", "formato"), ("gabinete", "formatos_admitidos"))
    if r := _falta_atributo(regla, faltantes, config):
        return r
    if formato in admitidos:
        return _resultado(regla, "cumple", f"El gabinete admite {formato}")
    return _resultado(regla, "no_cumple", f"La placa es {formato} y el gabinete admite {', '.join(admitidos)}")


def regla_largo_gpu_gabinete(config: Configuracion) -> ResultadoRegla:
    """No crítica: el catálogo real no informa largos. Un «no cumple» igual bloquea."""
    regla = "largo_gpu_gabinete"
    if r := _falta_pieza(regla, config, "gabinete", critica=False):
        return r
    (largo, maximo), faltantes = _atributos(config, ("gpu", "largo_mm"), ("gabinete", "largo_max_gpu_mm"))
    if r := _falta_atributo(regla, faltantes, config, critica=False):
        return r
    if largo <= maximo:
        return _resultado(regla, "cumple", f"La GPU mide {largo} mm y entran hasta {maximo} mm", critica=False)
    return _resultado(regla, "no_cumple", f"La GPU mide {largo} mm y el gabinete admite hasta {maximo} mm",
                      critica=False)


# --- Todas juntas ---------------------------------------------------------------------

def verificar_compatibilidad(config: Configuracion, margen_fuente: float = MARGEN_FUENTE) -> ReporteCompatibilidad:
    resultados = [
        regla_socket_cpu_placa(config),
        regla_generacion_cpu_placa(config),
        regla_tipo_ram(config),
        regla_modulo_ram(config),
        regla_ranuras_ram(config),
        regla_puertos_almacenamiento(config),
        regla_video(config),
        regla_cooler(config),
        regla_potencia_fuente(config, margen=margen_fuente),
        regla_formato_placa_gabinete(config),
    ]
    if "gpu" in config.componentes:
        resultados.append(regla_largo_gpu_gabinete(config))
        resultados.append(regla_conectores_gpu(config))
    if "cooler" in config.componentes:
        resultados.append(regla_socket_cooler(config))
        resultados.append(regla_potencia_cooler(config))
    return ReporteCompatibilidad(resultados=resultados)
