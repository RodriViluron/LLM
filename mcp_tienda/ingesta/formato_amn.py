"""Lector del formato de texto del catálogo real de la tienda (el mismo que usa hoy 3PC.PRG).

El catálogo no trae atributos estructurados, pero quien lo carga sigue una convención:

- `name` tiene 40 columnas. En CPU y placas madre la última palabra es el socket («... AM4», «... 1700»).
- `desc` (5 renglones) y `hdesc` (2 renglones) vienen PEGADOS, sin separador, en renglones de 50
  columnas. Lo primero es cortarlos: si no, «**SIN COOLER» + «NUCLEOS: 8» queda «**SIN COOLERNUCLEOS».
- Cada categoría anota sus datos con marcas fijas: «[12va]» (generación), «**SIN VIDEO», «65w»,
  «4 DDR4», «4 SATA3», «1 M.2 PCIe», «SOCKET: ...», «REQUIERE FUENTE 550W», «FORMATO: mATX, ATX»...

3PC.PRG lee esas marcas por posición o buscando la primera coincidencia en todo el texto. Eso falla
cuando alguien escribe «** SIN VIDEO» con un espacio, o cuando un cooler dice «VELOCIDAD: 1200 A
1800rpm» y el 1200 se toma por socket. Este lector busca cada dato solo en su lugar y, cuando no lo
entiende o dos lugares se contradicen, devuelve None («sin datos») y deja un aviso.

Los avisos no frenan nada: alimentan el reporte `evaluacion/calidad_catalogo.py`, que es la lista
de productos para corregir en el catálogo.
"""

import re
from dataclasses import dataclass, field

from mcp_tienda.esquemas import normalizar_texto
from mcp_tienda.ingesta import extraccion as generico
from mcp_tienda.modelos import ValorAtributo

ANCHO_RENGLON = 50

# Clases de aviso
ILEGIBLE = "ilegible"              # el dato no está donde la convención dice que va
CONTRADICCION = "contradiccion"    # dos lugares dicen cosas distintas
SIN_EVIDENCIA = "sin_evidencia"    # no hay ningún indicio del dato
FORMATO_PRG = "formato_prg"        # acá se lee bien, pero el sistema actual (3PC.PRG) lo lee mal

# Sockets con los que trabaja el armado (los mismos cinco de 3PC.PRG).
SOCKETS_ARMADO = generico.SOCKETS
ZOCALOS_LGA = {"775", "1150", "1151", "1155", "1156", "1200", "1366", "1700", "1851", "2011", "2066"}

# Cómo reconocer cada pieza: (categoría propia, códigos de categoría de la tienda, comienzo del nombre).
# Son las mismas condiciones que usa 3PC.PRG. Códigos None = alcanza con el nombre.
REGLAS_CATEGORIA: list[tuple[str, set[str] | None, str]] = [
    ("cpu", {"333"}, r"CPU\s"),
    ("motherboard", {"11"}, r"MB\."),
    ("ram", {"90"}, r"\d+GB\s+(?:SO-)?DDR\d"),
    ("gpu", None, r"PL\.VIDEO\s(?!USB)"),
    ("almacenamiento", {"93"}, r"D\.SSD\s"),
    ("almacenamiento", {"20"}, r"D\.DURO\s"),
    ("gabinete", {"180", "185", "186"}, r"GAB\."),
    ("fuente", {"145"}, r"FTE PC\s"),
    ("cooler", None, r"COOLER CPU\s"),
]


@dataclass(frozen=True)
class Aviso:
    atributo: str
    clase: str     # ILEGIBLE, CONTRADICCION, SIN_EVIDENCIA o FORMATO_PRG
    detalle: str   # escrito para quien carga el catálogo


@dataclass
class Lectura:
    categoria: str | None                      # None = no es una pieza del armado de PC
    atributos: dict[str, ValorAtributo] = field(default_factory=dict)
    avisos: list[Aviso] = field(default_factory=list)
    fuera_del_armado: str | None = None        # motivo, si la pieza no entra al armado (socket viejo, DDR3...)


class _Texto:
    """El producto ya cortado en renglones, más una bolsa para ir juntando avisos."""

    def __init__(self, nombre: str, desc: str, hdesc: str):
        self.nombre = (nombre or "").rstrip()
        self.desc = renglones(desc)
        self.hdesc = renglones(hdesc)
        self.lineas = self.desc + self.hdesc
        self.todo = "\n".join(self.lineas)
        self.avisos: list[Aviso] = []

    def avisar(self, atributo: str, clase: str, detalle: str) -> None:
        self.avisos.append(Aviso(atributo, clase, detalle))


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def renglones(texto: str | None, ancho: int = ANCHO_RENGLON) -> list[str]:
    """Corta el texto en renglones de `ancho` columnas, como se ve en la pantalla de carga."""
    texto = texto or ""
    return [texto[i:i + ancho].rstrip() for i in range(0, len(texto), ancho)]


def descripcion_publica(desc: str | None) -> str:
    """El campo `desc` con sus renglones separados, para guardar y mostrar."""
    return "\n".join(r for r in renglones(desc) if r.strip())


def clasificar(nombre: str, codigo_categoria: str | None) -> str | None:
    """Categoría propia de una pieza del armado, o None si el producto no es una."""
    for categoria, codigos, comienzo in REGLAS_CATEGORIA:
        if codigos is not None and codigo_categoria not in codigos:
            continue
        if re.match(comienzo, nombre or ""):
            return categoria
    return None


def _socket_del_nombre(t: _Texto) -> str | None:
    """Socket escrito al final del nombre: «AM4», «1700» (→ LGA1700), «FM2+»."""
    palabras = t.nombre.split()
    ultima = palabras[-1] if palabras else ""
    if re.fullmatch(r"\d{3,4}", ultima):
        return f"LGA{ultima}"
    if re.fullmatch(r"(?:AM|FM)\d\+?", ultima):
        return ultima
    t.avisar("socket", ILEGIBLE, f"el nombre no termina en un socket (termina en «{ultima}»)")
    return None


def _si_no(valor: bool) -> str:
    return "si" if valor else "no"


def _marca_sin(t: _Texto, atributo: str, palabra: str, exacta: str) -> bool:
    """¿Está la marca «**SIN <palabra>»? Acepta espacios de más y avisa si no está escrita como la espera el PRG."""
    m = re.search(rf"\*+\s*SIN\s*{palabra}", t.todo)
    if m and exacta not in t.todo:
        t.avisar(atributo, FORMATO_PRG, f"dice «{m.group(0)}»: 3PC.PRG busca «{exacta}» pegado y no lo encuentra")
    return bool(m)


# ---------------------------------------------------------------------------
# Lectores por categoría
# ---------------------------------------------------------------------------

def _cpu(t: _Texto) -> dict:
    socket = _socket_del_nombre(t)
    por_modelo = generico.socket_por_modelo_cpu(normalizar_texto(t.nombre))
    if socket and por_modelo and socket != por_modelo:
        t.avisar("socket", CONTRADICCION, f"el nombre termina en {socket} pero el modelo es de {por_modelo}")
        socket = None

    generacion = None
    if m := re.search(r"\[\s*(\d{1,2})\s*[a-z]{0,3}\s*\]", t.todo):
        generacion = str(int(m.group(1)))
    else:
        t.avisar("generacion", ILEGIBLE, "falta la generación entre corchetes, por ejemplo «[12va]»")

    # Núcleos: «NUCLEOS: 6», «NUCLEOS: 6P+0E», «NUCLEOS: 12 (CPU 4 + GPU 8)». El renglón de la GPU
    # integrada también puede decir NUCLEOS, por eso se busca en el renglón de SUBPROCESOS.
    nucleos = None
    for renglon in t.lineas:
        if "SUBPROCESOS" not in renglon:
            continue
        if m := re.search(r"NUCLEOS\s*:\s*\d+\s*\(\s*CPU\s*(\d+)", renglon):
            nucleos = int(m.group(1))
        elif m := re.search(r"NUCLEOS\s*:\s*(\d+)\s*P\s*\+\s*(\d+)\s*E", renglon):
            nucleos = int(m.group(1)) + int(m.group(2))
        elif m := re.search(r"NUCLEOS\s*:\s*(\d+)", renglon):
            nucleos = int(m.group(1))
        break

    # Consumo: «65w» (AMD) o «CONSUM.:65/117w» (Intel: base/máximo).
    consumos = {(int(a), int(b) if b else int(a))
                for a, b in re.findall(r"(?<![\w,.])(\d{2,3})\s*(?:/\s*(\d{2,3}))?\s*[wW]\b", t.todo)}
    consumos = {c for c in consumos if 10 <= c[0] <= c[1] <= 400}
    tdp = maximo = None
    if len(consumos) == 1:
        tdp, maximo = next(iter(consumos))
    elif consumos:
        t.avisar("tdp_w", CONTRADICCION, f"hay más de un consumo: {sorted(consumos)}")
    else:
        t.avisar("tdp_w", ILEGIBLE, "falta el consumo, por ejemplo «65w» o «CONSUM.:65/117w»")

    # Cooler: por convención trae cooler salvo que diga «**SIN COOLER».
    sin_cooler = _marca_sin(t, "incluye_cooler", "COOL", "**SIN COO")
    nombre_sin = bool(re.search(r"\bS/CO", t.nombre))
    nombre_con = bool(re.search(r"\bC/CO", t.nombre))
    incluye_cooler: str | None = _si_no(not sin_cooler)
    if sin_cooler and nombre_con:
        t.avisar("incluye_cooler", CONTRADICCION, "el nombre dice C/COOLER y la descripción «**SIN COOLER»")
        incluye_cooler = None
    elif not sin_cooler and nombre_sin:
        t.avisar("incluye_cooler", CONTRADICCION, "el nombre dice S/COOLER pero la descripción no trae «**SIN COOLER»")
        incluye_cooler = None

    # Video integrado: «**SIN VIDEO» = no tiene. Sin esa marca, tiene que nombrar la GPU integrada.
    sin_video = _marca_sin(t, "video_integrado", "VID", "**SIN VID")
    nombra_gpu = bool(re.search(r"\bGPU\b|GRAPHIC|RADEON|\bUHD\b|\bIRIS\b|\bVEGA\b", t.todo))
    modelo_sin_video = bool(re.search(r"\bS/VI", t.nombre) or re.search(r"\b\d{3,5}K?F\b", t.nombre))
    video_integrado: str | None
    if sin_video:
        video_integrado = "no"
    elif modelo_sin_video:
        t.avisar("video_integrado", CONTRADICCION,
                 "por el nombre es un modelo sin video, pero la descripción no trae «**SIN VIDEO»")
        video_integrado = None
    elif nombra_gpu:
        video_integrado = "si"
    else:
        t.avisar("video_integrado", SIN_EVIDENCIA, "no dice «**SIN VIDEO» ni nombra una GPU integrada")
        video_integrado = None

    return {"socket": socket, "generacion": generacion, "nucleos": nucleos, "tdp_w": tdp,
            "consumo_max_w": maximo, "incluye_cooler": incluye_cooler, "video_integrado": video_integrado}


def _motherboard(t: _Texto) -> dict:
    socket = _socket_del_nombre(t)
    renglon_chipset = next((r for r in t.lineas if re.search(r"\bCHIPSET\b|\bCH\.", r)), "")
    if m := re.search(r"(?:CHIPSET|CH\.)\s*(?:INTEL|AMD)\s+([A-Z]\d{2,3})", renglon_chipset):
        por_chipset = generico.CHIPSET_A_SOCKET.get(m.group(1).lower())
        if socket and por_chipset and socket != por_chipset:
            t.avisar("socket", CONTRADICCION,
                     f"el nombre termina en {socket} pero el chipset {m.group(1)} es de {por_chipset}")
            socket = None

    # Generaciones de CPU que soporta: entre paréntesis en el renglón del chipset,
    # «(12va,13va,14va GEN)», «(RYZEN 2da 3ra GEN)», «(2da SERIE)». Ojo: el renglón de las
    # ranuras PCIe también puede decir «(3ra GEN)», y esa es la generación de PCIe.
    generaciones = None
    if m := re.search(r"\(([^)]*)\)", renglon_chipset):
        encontradas = re.findall(r"(\d{1,2})\s*(?:ra|da|ta|va|ma|na)\b", m.group(1))
        generaciones = list(dict.fromkeys(str(int(g)) for g in encontradas)) or None
    if generaciones is None:
        t.avisar("generaciones", ILEGIBLE,
                 "falta la lista de generaciones en el renglón del chipset, por ejemplo «(12va,13va GEN)»")

    # Memoria: «4 DDR4 (MAX.128GB ...)» = 4 ranuras DDR4.
    tipo_ram = ranuras_ram = None
    if m := re.search(r"(?<![\w.,])(\d)\s+DDR(\d)\b", t.todo):
        ranuras_ram, tipo_ram = int(m.group(1)), f"DDR{m.group(2)}"
        en_nombre = re.search(r"\bD(?:DR)?([2-5])\b", t.nombre)
        if en_nombre and f"DDR{en_nombre.group(1)}" != tipo_ram:
            t.avisar("tipo_ram", CONTRADICCION,
                     f"el nombre dice DDR{en_nombre.group(1)} y la descripción {tipo_ram}")
            tipo_ram = None
    else:
        t.avisar("tipo_ram", ILEGIBLE, "falta «<ranuras> DDR<n>», por ejemplo «4 DDR4»")

    # Puertos SATA: «4 SATA3». No confundir con «1 M.2 SATA/PCIe» (ahí el 2 es de M.2).
    puertos_sata = None
    if m := re.search(r"(?<![\w.,])(\d{1,2})\s*SATA(?!\s*/)", t.todo):
        puertos_sata = int(m.group(1))
    else:
        t.avisar("puertos_sata", ILEGIBLE, "falta «<cantidad> SATA3», por ejemplo «4 SATA3»")

    # Ranuras M.2: «2 M.2 PCIe». Si no nombra M.2, la placa no tiene (así lo toma también el PRG).
    m = re.search(r"(?<![\w.,])(\d)\s*M\.2", t.todo)
    ranuras_m2 = int(m.group(1)) if m else 0
    if not m and "M.2" in t.todo:
        t.avisar("ranuras_m2", ILEGIBLE, "nombra M.2 pero sin la cantidad adelante, por ejemplo «2 M.2 PCIe»")
        ranuras_m2 = None

    formato = None
    if m := re.search(r"(?<![\w-])(E-?ATX|mATX|ATX|mITX|ITX)(?![\w-])", t.nombre):
        formato = {"EATX": "E-ATX", "E-ATX": "E-ATX", "mATX": "Micro-ATX", "ATX": "ATX",
                   "mITX": "Mini-ITX", "ITX": "Mini-ITX"}[m.group(1)]
    else:
        t.avisar("formato", ILEGIBLE, "el nombre no trae el formato (ATX, mATX, ITX)")

    return {"socket": socket, "generaciones": generaciones, "tipo_ram": tipo_ram, "ranuras_ram": ranuras_ram,
            "puertos_sata": puertos_sata, "ranuras_m2": ranuras_m2, "formato": formato}


def _bloque_socket(t: _Texto) -> str | None:
    """Texto desde «SOCKET» hasta el próximo renglón que empiece con otro rótulo («PESO:», «VELOCIDAD:»)."""
    for i, renglon in enumerate(t.lineas):
        pos = renglon.find("SOCKET")
        if pos < 0:
            continue
        bloque = [renglon[pos:]]
        for siguiente in t.lineas[i + 1:]:
            if re.match(r"\s*[A-Z][A-Z .]{3,}:", siguiente):
                break
            bloque.append(siguiente)
        return "\n".join(bloque)
    return None


def _sockets_en(texto: str) -> list[str]:
    """Sockets nombrados en un texto, sin confundirlos con velocidades (1200rpm) ni medidas."""
    encontrados: list[tuple[int, str]] = []
    for m in re.finditer(r"(?<![\w.])(\d{3,4})(?!\d|\s*(?:rpm|mm|cc|gr|w)\b|\s+A\s+\d)", texto, flags=re.I):
        if m.group(1) in ZOCALOS_LGA:
            encontrados.append((m.start(), f"LGA{m.group(1)}"))
    for m in re.finditer(r"(?<!\w)((?:AM|FM)\d\+?)(?![\w+])", texto):
        encontrados.append((m.start(), m.group(1)))
    return list(dict.fromkeys(s for _, s in sorted(encontrados)))


def _cooler(t: _Texto) -> dict:
    sockets = None
    bloque = _bloque_socket(t)
    if bloque is None:
        t.avisar("sockets", ILEGIBLE, "falta el renglón «SOCKET: ...» con la lista de sockets")
    else:
        sockets = _sockets_en(bloque) or None
        if sockets is None:
            t.avisar("sockets", ILEGIBLE, "el renglón «SOCKET:» no nombra ningún socket conocido")
        else:
            # 3PC.PRG busca el socket en todo el texto: un «1200» de las rpm lo da por compatible.
            fuera = [s for s in SOCKETS_ARMADO
                     if s not in sockets and s.removeprefix("LGA") in t.todo.replace(bloque, "")]
            if fuera:
                t.avisar("sockets", FORMATO_PRG,
                         f"{', '.join(fuera)} no está en «SOCKET:» pero el número aparece en otro renglón: "
                         "3PC.PRG lo da por compatible")

    en_desc = {int(x) for x in re.findall(r"ENFRIAMIENTO\s*:?\s*(\d{2,3})\s*w", t.todo, flags=re.I)}
    en_desc |= {int(x) for x in re.findall(r"\bTDP\s*:?\s*(\d{2,3})\s*w", t.todo, flags=re.I)}
    en_nombre = {int(x) for x in re.findall(r"(?<![\w.,])(\d{2,3})W\b", t.nombre)}
    potencia = None
    if len(en_desc | en_nombre) == 1:
        potencia = next(iter(en_desc | en_nombre))
    elif en_desc | en_nombre:
        t.avisar("potencia_enfriamiento_w", CONTRADICCION,
                 f"potencias distintas entre el nombre y la descripción: {sorted(en_desc | en_nombre)}")
    else:
        t.avisar("potencia_enfriamiento_w", ILEGIBLE,
                 "falta «PODER DE ENFRIAMIENTO: <n>w»: 3PC.PRG no lo ofrece para ninguna CPU")

    return {"sockets": sockets, "potencia_enfriamiento_w": potencia, "altura_mm": None}


def _ram(t: _Texto) -> dict:
    m = re.match(r"(\d+)GB\s+(SO-)?DDR(\d),\s*(\d{3,4})", t.nombre)
    if not m:
        t.avisar("capacidad_gb", ILEGIBLE, "el nombre no sigue «<n>GB  DDR<n>,<frecuencia>»")
        return {"tipo": None, "capacidad_gb": None, "frecuencia_mhz": None, "modulos": None, "formato_modulo": None}
    capacidad, so, tipo, frecuencia = int(m.group(1)), bool(m.group(2)), f"DDR{m.group(3)}", int(m.group(4))

    # Kit: «K2x8» en el nombre y «ES UN KIT DE 2 MEMORIAS» en la descripción.
    modulos: int | None = 1
    kit_nombre = re.search(r"\bK(\d)x(\d+)", t.nombre)
    kit_desc = re.search(r"ES UN KIT DE (\d)", t.todo)
    if kit_nombre or kit_desc:
        cantidades = {int(k.group(1)) for k in (kit_nombre, kit_desc) if k}
        modulos = next(iter(cantidades)) if len(cantidades) == 1 else None
        if kit_nombre and int(kit_nombre.group(1)) * int(kit_nombre.group(2)) != capacidad:
            modulos = None
        if modulos is None:
            t.avisar("modulos", CONTRADICCION, "el kit del nombre, el de la descripción y la capacidad no coinciden")
        elif not (kit_nombre and kit_desc):
            t.avisar("modulos", SIN_EVIDENCIA,
                     "es un kit según un solo lugar: 3PC.PRG necesita «ES UN KIT DE 2» en la descripción")

    sodimm_desc = bool(re.search(r"SO-?DIMM", t.todo))
    if re.search(r"\bRDIMM\b|\bECC\b|REGISTERED", f"{t.nombre}\n{t.todo}"):
        formato_modulo = "ECC"            # memoria de servidor: no va en una PC de escritorio
    elif so or sodimm_desc:
        formato_modulo = "SODIMM"         # memoria de notebook
        if so != sodimm_desc:
            t.avisar("formato_modulo", CONTRADICCION, "SO-DIMM según el nombre o la descripción, pero no en los dos")
    elif re.search(r"\bU?DIMM\b", t.todo):
        formato_modulo = "DIMM"
    else:
        formato_modulo = None
        t.avisar("formato_modulo", SIN_EVIDENCIA, "la descripción no dice si es DIMM o SODIMM")

    if formato_modulo == "DIMM" and tipo in ("DDR4", "DDR5") and not re.search(r"\s{2}DDR", t.nombre):
        t.avisar("tipo", FORMATO_PRG, "hay un solo espacio antes de DDR: 3PC.PRG exige dos y no la ofrece")

    return {"tipo": tipo, "capacidad_gb": capacidad, "frecuencia_mhz": frecuencia, "modulos": modulos,
            "formato_modulo": formato_modulo}


def _gpu(t: _Texto) -> dict:
    vram = None
    if m := re.search(r"(?<![\w.,])(\d{1,2})G/", t.nombre):
        vram = int(m.group(1))
    else:
        t.avisar("vram_gb", ILEGIBLE, "el nombre no trae la memoria como «8G/D6/2F»")

    # «REQUIERE FUENTE 550W+POWER 1x8pin», «FUENTE RECOMENDADA 500W», «FUENTE MIN.450W RECOMENDADA 550W».
    # Si hay mínima y recomendada, vale la recomendada (la más alta).
    potencias = [int(x) for r in t.lineas if "FUENTE" in r
                 for x in re.findall(r"(?<!\d)(?<!\d[.,])(\d{3,4})\s*W\b", r)]
    fuente = max(potencias) if potencias else None
    if fuente is None:
        t.avisar("fuente_recomendada_w", ILEGIBLE, "falta «REQUIERE FUENTE <n>W»")

    # Conector de energía: «+POWER 1x8pin» o «+ 1 POWER 8pin».
    conector = None
    if m := (re.search(r"POWER\s*(?P<n>\d)\s*x\s*(?P<pines>\d{1,2})\s*pin", t.todo)
             or re.search(r"(?P<n>\d)\s*POWER\s*(?P<pines>\d{1,2})\s*pin", t.todo)):
        conector = f"{int(m['n'])}x{int(m['pines'])}pin"

    return {"vram_gb": vram, "fuente_recomendada_w": fuente, "conectores_energia": conector,
            "consumo_w": None, "largo_mm": None}


def _gabinete(t: _Texto) -> dict:
    # Fuente: «S/FT» en el nombre = sin fuente; «600W» en el nombre = la trae.
    sin_fuente = bool(re.search(r"\bS/F", t.nombre))
    watts = re.findall(r"(?<![\w.,])(\d{3,4})W\b", t.nombre)
    texto_sin = "NO INCLUYE FUENTE" in t.todo
    incluye_fuente = potencia = None
    if sin_fuente and not watts:
        incluye_fuente = "no"
    elif watts and not sin_fuente and not texto_sin:
        incluye_fuente, potencia = "si", int(watts[0])
    elif sin_fuente or watts:
        t.avisar("incluye_fuente", CONTRADICCION, "el nombre y la descripción no coinciden en si trae fuente")
    else:
        t.avisar("incluye_fuente", ILEGIBLE, "el nombre no dice «S/FT» ni los watts de la fuente incluida")

    # «FORMATO: mATX, ATX, E-ATX -FAN: 3x120mm»: se lee hasta el « -» que abre el dato siguiente.
    admitidos = None
    renglon = next((r for r in t.lineas if "FORMATO" in r), None)
    if renglon is None:
        t.avisar("formatos_admitidos", ILEGIBLE, "falta el renglón «FORMATO: ...»")
    else:
        segmento = re.split(r"\s-", renglon[renglon.find("FORMATO"):])[0]
        formatos = generico.encontrar_formatos(normalizar_texto(segmento))
        if formatos:
            # El formato más grande que admite implica los más chicos (igual que en el lector de texto libre).
            admitidos = list(generico.FORMATOS[generico.FORMATOS.index(formatos[0]):])
        else:
            t.avisar("formatos_admitidos", ILEGIBLE, f"no se reconoce ningún formato en «{segmento.strip()}»")

    return {"formatos_admitidos": admitidos, "incluye_fuente": incluye_fuente, "potencia_fuente_w": potencia,
            "largo_max_gpu_mm": None}


CERTIFICACIONES = {"WHT": "White", "WHITE": "White", "BZE": "Bronze", "BRONZE": "Bronze", "SLV": "Silver",
                   "SILVER": "Silver", "GLD": "Gold", "GOLD": "Gold", "PLT": "Platinum", "PLATINUM": "Platinum",
                   "TIT": "Titanium", "TITANIUM": "Titanium"}


def _fuente(t: _Texto) -> dict:
    potencia = None
    if m := re.search(r"(?<![\w.,])(\d{3,4})W\b", t.nombre):
        potencia = int(m.group(1))
    else:
        t.avisar("potencia_w", ILEGIBLE, "el nombre no trae los watts, por ejemplo «650W»")

    niveles = {CERTIFICACIONES[x] for x in re.findall(r"80\+\s*([A-Z]+)", f"{t.nombre}\n{t.todo}")
               if x in CERTIFICACIONES}
    certificacion = f"80 Plus {next(iter(niveles))}" if len(niveles) == 1 else None
    if len(niveles) > 1:
        t.avisar("certificacion", CONTRADICCION, f"certificaciones distintas: {sorted(niveles)}")

    # Conectores para placa de video: «4 PCIe 6+2pin». Si la lista de conectores está y no nombra PCIe, son 0.
    cantidades = [int(x) for x in re.findall(r"(?<![\w.,])(\d)\s*PCIe\s*(?:6\+2|6|8)\s*pin", t.todo)]
    if cantidades:
        conectores = sum(cantidades)
    elif re.search(r"POWER\s*20\+4", t.todo):
        conectores = 0
    else:
        conectores = None

    return {"potencia_w": potencia, "certificacion": certificacion, "conectores_pcie": conectores}


def _almacenamiento(t: _Texto) -> dict:
    if re.match(r"D\.SSD\s+M\.2\s+PCIe", t.nombre):
        tipo, conexion = "NVMe", "M.2"
    elif re.match(r"D\.SSD\s+M\.2\s+SATA", t.nombre):
        tipo, conexion = "M.2 SATA", "M.2"
    elif re.match(r"D\.SSD\s+2,5", t.nombre):
        tipo, conexion = "SSD SATA", "SATA"
    elif re.match(r"D\.DURO\s", t.nombre):
        tipo, conexion = "HDD", "SATA" if "SATA" in f"{t.nombre}\n{t.todo}" else None
    else:
        tipo = conexion = None
        t.avisar("tipo", ILEGIBLE, "el nombre no empieza como «D.SSD  M.2 PCIe», «D.SSD  2,5\"» o «D.DURO SATA3»")

    def a_gb(valor: str, unidad: str) -> int:
        n = float(valor.replace(",", "."))
        return round(n * 1000) if unidad == "TB" else round(n)

    capacidad = None
    en_nombre = re.search(r"(?<![\w.,])(\d+(?:,\d+)?)\s*(TB|GB)\b", t.nombre)
    en_desc = re.search(r"CAPACIDAD\s*:\s*(\d+(?:,\d+)?)\s*(TB|GB)\b", t.todo)
    valores = {a_gb(*m.groups()) for m in (en_nombre, en_desc) if m}
    if len(valores) == 1:
        capacidad = next(iter(valores))
    elif valores:
        t.avisar("capacidad_gb", CONTRADICCION,
                 f"capacidades distintas entre el nombre y la descripción: {sorted(valores)}")
    else:
        t.avisar("capacidad_gb", ILEGIBLE, "ni el nombre ni «CAPACIDAD:» traen la capacidad")

    return {"tipo": tipo, "conexion": conexion, "capacidad_gb": capacidad}


LECTORES = {"cpu": _cpu, "motherboard": _motherboard, "cooler": _cooler, "ram": _ram, "gpu": _gpu,
            "gabinete": _gabinete, "fuente": _fuente, "almacenamiento": _almacenamiento}


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def _motivo_fuera_del_armado(categoria: str, crudos: dict) -> str | None:
    """Piezas legítimas que el armado no usa (plataformas viejas). No son errores del catálogo."""
    if categoria in ("cpu", "motherboard") and crudos.get("socket") and crudos["socket"] not in SOCKETS_ARMADO:
        return f"socket {crudos['socket']}: plataforma que el armado no ofrece"
    if categoria == "ram":
        if crudos.get("tipo") and crudos["tipo"] not in ("DDR4", "DDR5"):
            return f"{crudos['tipo']}: memoria de una plataforma que el armado no ofrece"
        if crudos.get("formato_modulo") in ("SODIMM", "ECC"):
            return f"módulo {crudos['formato_modulo']}: no es memoria de PC de escritorio"
    return None


def leer(nombre: str, desc: str | None, hdesc: str | None, codigo_categoria: str | None) -> Lectura:
    """Lee un producto del catálogo de la tienda. Los atributos salen ya validados contra el esquema."""
    categoria = clasificar(nombre, codigo_categoria)
    if categoria is None:
        return Lectura(categoria=None)
    texto = _Texto(nombre, desc or "", hdesc or "")
    crudos = LECTORES[categoria](texto)
    motivo = _motivo_fuera_del_armado(categoria, crudos)
    return Lectura(
        categoria=categoria,
        atributos=generico.validar_contra_esquema(categoria, crudos),
        avisos=[] if motivo else texto.avisos,   # a una pieza que el armado no usa no se le reclama nada
        fuera_del_armado=motivo,
    )
