"""Extracción de atributos con reglas y expresiones regulares.

Principio: si el texto no deja claro un dato, se devuelve None («sin datos»). Un None es seguro
(la regla de compatibilidad avisa que falta el dato); un valor equivocado es peligroso (puede dar
por compatible algo que no lo es). Por eso, ante dos valores distintos para el mismo atributo,
se devuelve None en vez de elegir uno.

Hay pocas inferencias, y todas son deterministas y conocidas:
- socket de la placa a partir del chipset (B550 → AM4) y de la CPU a partir del modelo (i5-12400 → LGA1700),
- formato Micro-ATX cuando el chipset de la placa termina en M (B550M),
- formatos admitidos por un gabinete: el formato más grande que admite implica los más chicos.

El respaldo con LLM para lo que las regex no resuelvan queda para una fase posterior.
"""

import html
import re

from mcp_tienda.esquemas import cargar_esquemas, normalizar_texto
from mcp_tienda.modelos import ValorAtributo

SOCKETS = ("AM4", "AM5", "LGA1200", "LGA1700", "LGA1851")
FORMATOS = ("E-ATX", "ATX", "Micro-ATX", "Mini-ITX")  # de mayor a menor

CHIPSET_A_SOCKET = {
    **dict.fromkeys(["a320", "b350", "x370", "b450", "x470", "a520", "b550", "x570"], "AM4"),
    **dict.fromkeys(["a620", "b650", "x670", "b850", "x870"], "AM5"),
    **dict.fromkeys(["h410", "b460", "h470", "z490", "h510", "b560", "h570", "z590"], "LGA1200"),
    **dict.fromkeys(["h610", "b660", "h670", "z690", "b760", "h770", "z790"], "LGA1700"),
    **dict.fromkeys(["h810", "b860", "z890"], "LGA1851"),
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def limpiar_texto(texto: str) -> str:
    """Saca HTML, pasa a minúsculas sin tildes y deja un salto de línea entre frases."""
    texto = re.sub(r"<\s*(br|/p|/li|/div)\s*/?>", "\n", texto, flags=re.I)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto).replace("\xa0", " ")
    lineas = [normalizar_texto(linea) for linea in re.split(r"\n|(?<=[a-z0-9)])\.\s", texto, flags=re.I)]
    return "\n".join(linea for linea in lineas if linea)


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


def _unico(valores: list) -> ValorAtributo:
    """Devuelve el valor si todos coinciden; None si no hay o si hay contradicción."""
    distintos = list(dict.fromkeys(valores))
    return distintos[0] if len(distintos) == 1 else None


def _a_mm(valor: str, unidad: str) -> int:
    n = _numero(valor)
    return round(n * 10) if unidad == "cm" else round(n)


# ---------------------------------------------------------------------------
# Extractores reutilizables
# ---------------------------------------------------------------------------

def encontrar_sockets(t: str) -> list[str]:
    """Todos los sockets mencionados, en orden y sin repetir. Entiende listas «LGA1700/1200»."""
    encontrados: list[tuple[int, str]] = []
    for m in re.finditer(r"\bs?am\s?-?\s?([45](?:\s*/\s*(?:am)?\s*[45])*)\b", t):
        for n in re.findall(r"[45]", m.group(1)):
            encontrados.append((m.start(), f"AM{n}"))
    patron_lga = r"\b(?:fc)?lga\s*-?\s*(\d{4}x?(?:\s*[/,]\s*\d{4}x?|\s+\d{4}x?)*)"
    for m in re.finditer(patron_lga, t):
        for n in re.findall(r"\d{4}", m.group(1)):
            encontrados.append((m.start(), f"LGA{n}"))
    for m in re.finditer(r"\b(?:socket|zocalo)\s*-?\s*(\d{4})\b", t):
        encontrados.append((m.start(), f"LGA{m.group(1)}"))
    ordenados = [s for _, s in sorted(encontrados)]
    return [s for s in dict.fromkeys(ordenados) if s in SOCKETS]


def socket_por_modelo_cpu(t: str) -> str | None:
    """Socket deducido del modelo de CPU (es un dato fijo de cada generación)."""
    if m := re.search(r"ryzen\s*[3579]\s*(\d)\d{3}", t):
        gen = int(m.group(1))
        return "AM4" if gen <= 5 else "AM5" if gen in (7, 8, 9) else None
    if m := re.search(r"\bi[3579]\s*-?\s*(\d{2})\d{3}", t):
        gen = int(m.group(1))
        return "LGA1200" if gen in (10, 11) else "LGA1700" if gen in (12, 13, 14) else None
    if re.search(r"\bultra\s*[3579]\s*2\d{2}", t):
        return "LGA1851"
    return None


def encontrar_chipset(t: str) -> tuple[str, bool] | None:
    """(chipset, termina_en_m). Ej.: «b550m ds3h» → ("b550", True)."""
    for m in re.finditer(r"\b([abhxz]\d{3})(m?)(?:e)?\b", t):
        if m.group(1) in CHIPSET_A_SOCKET:
            return m.group(1), bool(m.group(2))
    return None


def encontrar_formatos(t: str) -> list[str]:
    """Formatos de placa mencionados. Ignora el conector «ATX de 24 pines» y la «fuente ATX»."""
    t = re.sub(r"\batx\s*(de\s*)?\d+\s*pin\w*", " ", t)
    t = re.sub(r"\b(fuente|psu)\s*(de\s*poder\s*)?(atx|sfx)\b", " ", t)
    encontrados = []
    patrones = [
        ("E-ATX", r"\be-?atx\b"),
        ("Micro-ATX", r"\bmicro[\s-]?atx\b|\bm-?atx\b|\buatx\b"),
        ("Mini-ITX", r"\bmini[\s-]?itx\b|\bm-?itx\b|\bitx\b"),
    ]
    for formato, patron in patrones:
        if re.search(patron, t):
            encontrados.append(formato)
        t = re.sub(patron, " ", t)
    if re.search(r"\batx\b", t):
        encontrados.append("ATX")
    return [f for f in FORMATOS if f in encontrados]


def encontrar_ddr(t: str, permitir_d4: bool = False) -> str | None:
    tipos = [f"DDR{n}" for n in re.findall(r"\bddr\s?-?\s?([45])\b", t)]
    if permitir_d4:
        tipos += [f"DDR{n}" for n in re.findall(r"[\s-]d([45])\b", t)]
    return _unico(tipos)


def encontrar_watts(t: str, excluir_pico: bool = True) -> list[int]:
    valores = []
    for m in re.finditer(r"(?<![\d.,])(\d{2,4})\s*(?:w|watts?|vatios)\b", t):
        previo = t[max(0, m.start() - 15):m.start()]
        if excluir_pico and re.search(r"pico|peak|maxim", previo):
            continue
        valores.append(int(m.group(1)))
    return valores


# ---------------------------------------------------------------------------
# Extractores por categoría. Reciben nombre y descripción ya limpios.
# ---------------------------------------------------------------------------

def _cpu(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    socket = _unico(encontrar_sockets(t)) or socket_por_modelo_cpu(nombre)
    nucleos = None
    patrones = [r"\b(\d{1,2})\s*(?:nucleos|cores?)\b", r"\b(\d{1,2})\s*c\s*/\s*\d{1,2}\s*t\b",
                r"nucleos\s*:?\s*(\d{1,2})\b"]
    nucleos = _unico([int(x) for p in patrones for x in re.findall(p, t)])
    tdp = re.findall(r"tdp\)?\s*(?:de\s*|:\s*)?(\d{2,3})\s*(?:w|watts?)\b", t)
    tdp += re.findall(r"(\d{2,3})\s*(?:w|watts?)\s*(?:de\s*)?tdp\b", t)
    return {"socket": socket, "nucleos": nucleos, "tdp_w": _unico([int(x) for x in tdp])}


def _motherboard(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    chipset = encontrar_chipset(t)
    socket = _unico(encontrar_sockets(t))
    if socket is None and chipset:
        socket = CHIPSET_A_SOCKET[chipset[0]]
    formatos = encontrar_formatos(t)
    formato = formatos[0] if len(formatos) == 1 else None
    if not formatos and chipset and chipset[1]:
        formato = "Micro-ATX"
    return {"socket": socket, "tipo_ram": encontrar_ddr(t, permitir_d4=True), "formato": formato}


def _ram(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    kits = [int(a) * int(b) for a, b in re.findall(r"\b(\d)\s*x\s*(\d{1,2})\s*gb\b", t)]
    capacidad = _unico(kits) if kits else _unico([int(x) for x in re.findall(r"\b(\d{1,3})\s*gb\b", t)])
    frecuencias = re.findall(r"\b(\d{4})\s*(?:mhz|mt/?s)\b", t)
    frecuencias += re.findall(r"\bddr[45]\s?-?\s?(\d{4})\b", t)
    return {"tipo": encontrar_ddr(t), "capacidad_gb": capacidad,
            "frecuencia_mhz": _unico([int(x) for x in frecuencias])}


def _gpu(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    vram = _unico([int(x) for x in re.findall(r"\b(\d{1,2})\s*gb?\b", t)])
    consumo = re.findall(r"(?:consumo|tbp|tgp|potencia de la placa)[^\d\n]{0,30}?(\d{2,3})\s*(?:w|watts?)\b", t)
    largos = [_a_mm(v, u) for v, u in re.findall(
        r"(?:largo|longitud|length)[^\d\n]{0,15}?(\d{2,3}(?:[.,]\d)?)\s*(mm|cm)\b", t)]
    largos += [_a_mm(v, u) for v, u in re.findall(
        r"(\d{2,3}(?:[.,]\d)?)\s*(?:mm\s*)?x\s*\d{2,3}(?:[.,]\d)?\s*(?:mm\s*)?x\s*\d{2,3}(?:[.,]\d)?\s*(mm|cm)\b", t)]
    return {"vram_gb": vram, "consumo_w": _unico([int(x) for x in consumo]), "largo_mm": _unico(largos)}


def _almacenamiento(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    if re.search(r"\bnvme\b|\bpcie\b", t):
        tipo = "NVMe"
    elif re.search(r"\bhdd\b|disco (rigido|duro|mecanico)|\b\d{4}\s*rpm\b", t):
        tipo = "HDD"
    elif re.search(r"\bssd\b|solido", t) and re.search(r"\bsata\b|2[.,]5", t):
        tipo = "SSD SATA"
    else:
        tipo = None  # «SSD» a secas no alcanza para saber si es SATA o NVMe
    capacidades = [round(_numero(x) * 1000) for x in re.findall(r"\b(\d{1,2}(?:[.,]\d)?)\s*tb\b", t)]
    capacidades += [int(x) for x in re.findall(r"\b(\d{3,4})\s*gb\b", t)]
    return {"tipo": tipo, "capacidad_gb": _unico(capacidades)}


def _fuente(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    potencias = [w for w in encontrar_watts(t) if 300 <= w <= 2000]
    potencia = _unico(potencias)
    if not potencias:
        # Respaldo: el número del modelo (CV650, RM750e, GP-550), solo en el nombre.
        candidatos = [int(x) for x in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", nombre)]
        potencia = _unico([x for x in candidatos if 300 <= x <= 2000 and x % 50 == 0])
    if re.search(r"sin certificacion", t):
        certificacion = "Sin certificación"
    else:
        colores = {"white": "White", "bronze": "Bronze", "bronce": "Bronze", "silver": "Silver",
                   "plata": "Silver", "gold": "Gold", "oro": "Gold", "platinum": "Platinum",
                   "platino": "Platinum", "titanium": "Titanium", "titanio": "Titanium"}
        encontrados = []
        for m in re.finditer(r"\b80\s*(?:\+|plus\b)\s*(white|bronze|bronce|silver|plata|gold|oro|platinum"
                             r"|platino|titanium|titanio)?", t):
            encontrados.append(colores[m.group(1)] if m.group(1) else "White")
        if not encontrados:
            encontrados = [colores[c] for c in re.findall(
                r"\b(bronze|bronce|silver|gold|platinum|titanium)\b", t)]
        color = _unico(encontrados)
        certificacion = f"80 Plus {color}" if color else None
    return {"potencia_w": potencia, "certificacion": certificacion}


def _gabinete(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    formatos = encontrar_formatos(t)
    admitidos = list(FORMATOS[FORMATOS.index(formatos[0]):]) if formatos else None
    largos = [_a_mm(v, u) for v, u in re.findall(
        r"(?:placas?\s*de\s*video|gpu|vga|tarjetas?\s*graficas?)[^\d.;\n]{0,30}?(\d{2,3}(?:[.,]\d)?)\s*(mm|cm)\b", t)]
    return {"formatos_admitidos": admitidos, "largo_max_gpu_mm": _unico(largos)}


def _cooler(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    alturas = [_a_mm(v, u) for v, u in re.findall(
        r"\b(?:altura|alto|height)\s*(?:total\s*)?(?:de\s*|:\s*)?(\d{2,3}(?:[.,]\d)?)\s*(mm|cm)\b", t)]
    return {"sockets": encontrar_sockets(t) or None, "altura_mm": _unico(alturas)}


def _ups(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    va = _unico([int(x) for x in re.findall(r"\b(\d{3,4})\s*va\b", t)])
    w = _unico([x for x in encontrar_watts(t) if x >= 100])
    autonomia = _unico([int(x) for x in re.findall(r"\b(\d{1,3})\s*(?:min|minutos)\b", t)])
    return {"va": va, "w": w, "autonomia_minutos": autonomia}


PATRONES_CONECTOR = [
    ("DisplayPort", r"\bdisplay\s?port\b|\bdp\b"),
    ("HDMI", r"\bhdmi\b"),
    ("USB-C", r"\busb[\s-]?(?:tipo\s*)?c\b|\btype[\s-]?c\b"),
    ("USB-A", r"\busb[\s-]?(?:\d\.\d\s*)?(?:tipo\s*)?a\b"),
    ("VGA", r"\bvga\b|\bd-?sub\b"),
    ("RJ45", r"\brj-?45\b|\butp\b"),
    ("C13", r"\bc13\b"),
    ("C14", r"\bc14\b"),
]


def _cables(nombre: str, desc: str) -> dict:
    t = f"{nombre}\n{desc}"
    t = re.sub(r"\bdp\s*alt\s*mode\b|displayport\s*alt\s*mode", " ", t)
    encontrados = []
    for conector, patron in PATRONES_CONECTOR:
        encontrados += [(m.start(), conector) for m in re.finditer(patron, t)]
    orden = list(dict.fromkeys(c for _, c in sorted(encontrados)))
    if not orden and "interlock" in t:
        orden = ["C14", "C13"]
    conector_a = orden[0] if orden else None
    conector_b = orden[1] if len(orden) > 1 else conector_a
    largos = [_numero(x) for x in re.findall(r"(?<![\d.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:m|mts?|metros?)\b", t)]
    largos += [int(x) / 100 for x in re.findall(r"(?<![\d.,])(\d{2,4})\s*cm\b", t)]
    return {"conector_a": conector_a, "conector_b": conector_b,
            "largo_m": _unico([round(x, 2) for x in largos])}


EXTRACTORES = {
    "cpu": _cpu, "motherboard": _motherboard, "ram": _ram, "gpu": _gpu,
    "almacenamiento": _almacenamiento, "fuente": _fuente, "gabinete": _gabinete,
    "cooler": _cooler, "ups": _ups, "cables": _cables,
}


def extraer_atributos(categoria: str, nombre: str, descripcion: str) -> dict[str, ValorAtributo]:
    """Atributos del esquema de la categoría. Los que no se pueden extraer quedan en None.

    Los valores de tipo texto o lista se validan contra los valores permitidos del esquema:
    si la regex devolvió algo fuera del esquema, se descarta (None).
    """
    if categoria not in EXTRACTORES:
        return {}
    return validar_contra_esquema(categoria, EXTRACTORES[categoria](limpiar_texto(nombre), limpiar_texto(descripcion)))


def validar_contra_esquema(categoria: str, crudos: dict) -> dict[str, ValorAtributo]:
    """Deja solo los atributos del esquema; lo que falta o está fuera de los valores permitidos queda en None.

    La usan los dos lectores: el de texto libre (este archivo) y el del formato de la tienda (formato_amn.py).
    """
    esquema = cargar_esquemas().get(categoria)
    if esquema is None:
        return {}
    atributos: dict[str, ValorAtributo] = {}
    for clave, definicion in esquema.atributos.items():
        valor = crudos.get(clave)
        if valor is not None and definicion.valores:
            permitidos = set(definicion.valores) | set(definicion.valores_fuera_del_armado or [])
            if isinstance(valor, list):
                valor = [v for v in valor if v in permitidos] or None
            elif valor not in permitidos:
                valor = None
        atributos[clave] = valor
    return atributos
