"""Genera el catálogo de prueba desprolijo (escenario B) a partir de las semillas.

Las descripciones se ensucian a propósito, como en una tienda real:
- el mismo dato escrito de varias formas («AM4», «Socket AM-4», «sAM4»; «22,7 cm» en vez de mm),
- atributos que faltan (se omiten con probabilidad P_OMITIR),
- distractores que una regex ingenua confunde («Fuente recomendada: 550W» en una placa de video,
  «Conector ATX de 24 pines» en una placa Micro-ATX, «Potencia pico 600W» en una fuente de 500W),
- restos de HTML, mayúsculas y texto comercial.

Salidas (determinísticas, con semilla fija):
- datos/catalogo_prueba/productos_crudos.json  lista de ProductoCrudo
- datos/catalogo_prueba/etiquetas.json         la verdad: categoría y atributos por código

Uso:  python -m mcp_tienda.ingesta.generar_catalogo_prueba
"""

import json
import random

import yaml

from mcp_tienda.config import DIR_CATALOGO_PRUEBA
from mcp_tienda.modelos import ProductoCrudo

SEMILLA = 10
P_OMITIR = 0.15

PREFIJO_CODIGO = {
    "cpu": "CPU", "motherboard": "MOT", "ram": "RAM", "gpu": "GPU", "almacenamiento": "ALM",
    "fuente": "FUE", "gabinete": "GAB", "cooler": "COO", "ups": "UPS", "cables": "CAB",
}

CATEGORIA_ORIGEN = {
    "cpu": ["Procesadores", "Micros {marca}", "PROCESADORES", "Microprocesadores"],
    "motherboard": ["Motherboards", "Mothers {marca}", "Placas Madre", "MOTHERBOARDS"],
    "ram": ["Memorias RAM", "Memorias", "MEMORIAS {tipo}", "Memorias {tipo}"],
    "gpu": ["Placas de Video", "Tarjetas Gráficas", "PLACAS DE VIDEO"],
    "almacenamiento": ["Almacenamiento", "Discos SSD", "Discos Rígidos", "ALMACENAMIENTO"],
    "fuente": ["Fuentes", "Fuentes de Alimentación", "FUENTES"],
    "gabinete": ["Gabinetes", "GABINETES"],
    "cooler": ["Coolers", "Refrigeración CPU", "Coolers y Disipadores"],
    "ups": ["UPS", "Estabilizadores y UPS"],
    "cables": ["Cables", "Cables y Adaptadores", "CABLES"],
}

TEXTO_COMERCIAL = [
    "¡Envío gratis en Mendoza!", "Garantía oficial 12 meses.", "Consultá stock antes de comprar.",
    "Producto original, sellado.", "Retiro en local sin cargo.", "PRECIO CONTADO / TRANSFERENCIA.",
    "Factura A y B.",
]


# ---------------------------------------------------------------------------
# Variantes de escritura de cada dato
# ---------------------------------------------------------------------------

def _decimal(x: float, r: random.Random) -> str:
    """1.8 -> «1.8» o «1,8» (en Argentina se usa mucho la coma)."""
    texto = f"{x:g}"
    return texto.replace(".", ",") if r.random() < 0.5 else texto


def v_socket(s: str, r: random.Random) -> str:
    if s.startswith("AM"):
        n = s[2:]
        return r.choice([f"AM{n}", f"am{n}", f"Socket AM{n}", f"socket AM-{n}", f"sAM{n}", f"AM {n}"])
    n = s[3:]
    return r.choice([f"LGA{n}", f"LGA {n}", f"lga{n}", f"FCLGA{n}", f"Socket {n}", f"socket LGA-{n}"])


def v_ddr(t: str, r: random.Random) -> str:
    n = t[-1]
    return r.choice([f"DDR{n}", f"ddr{n}", f"DDR-{n}", f"DDR {n}"])


def v_formato(f: str, r: random.Random) -> str:
    return r.choice({
        "E-ATX": ["E-ATX", "EATX", "e-atx"],
        "ATX": ["ATX", "atx"],
        "Micro-ATX": ["Micro-ATX", "Micro ATX", "mATX", "M-ATX", "uATX", "micro atx"],
        "Mini-ITX": ["Mini-ITX", "Mini ITX", "mITX", "ITX"],
    }[f])


def v_w(w: int, r: random.Random) -> str:
    return r.choice([f"{w}W", f"{w} W", f"{w} watts", f"{w}w", f"{w} Watts"])


def v_mm(mm: int, r: random.Random) -> str:
    if r.random() < 0.3:
        return f"{_decimal(mm / 10, r)} cm"
    return r.choice([f"{mm} mm", f"{mm}mm", f"{mm} MM"])


def v_gb(n: int, r: random.Random) -> str:
    return r.choice([f"{n}GB", f"{n} GB", f"{n}gb", f"{n} Gb"])


def v_capacidad_disco(gb: int, r: random.Random) -> str:
    if gb >= 1000:
        tb = gb // 1000
        return r.choice([f"{tb}TB", f"{tb} TB", f"{gb}GB", f"{tb} Tb"])
    return r.choice([f"{gb}GB", f"{gb} GB", f"{gb}gb"])


def v_frecuencia(mhz: int, tipo: str, r: random.Random) -> str:
    return r.choice([f"{mhz}MHz", f"{mhz} MHz", f"{mhz}mhz", f"{tipo}-{mhz}", f"{mhz} MT/s"])


def v_certificacion(c: str, r: random.Random) -> str:
    if c == "Sin certificación":
        return r.choice(["Sin certificación", "Sin certificación 80 Plus"])
    if c == "80 Plus White":
        return r.choice(["80 Plus", "80 Plus White", "80+ White", "80PLUS"])
    color = c.split()[-1]
    variantes_color = {"Bronze": ["Bronze", "BRONZE", "Bronce"], "Gold": ["Gold", "GOLD"]}
    col = r.choice(variantes_color.get(color, [color]))
    return r.choice([f"80 Plus {col}", f"80+ {col}", f"80 PLUS {col}", f"80Plus {col}",
                     f"certificación {col}"])


def v_largo_m(m: float, r: random.Random) -> str:
    if r.random() < 0.2:
        return f"{round(m * 100)} cm"
    return r.choice([f"{_decimal(m, r)} m", f"{_decimal(m, r)} mts", f"{_decimal(m, r)}mts",
                     f"{_decimal(m, r)} metros", f"{_decimal(m, r)}m"])


def v_conector(c: str, r: random.Random) -> str:
    return r.choice({
        "HDMI": ["HDMI", "hdmi", "Hdmi"],
        "DisplayPort": ["DisplayPort", "Display Port", "DP"],
        "USB-C": ["USB-C", "USB Tipo C", "Type-C", "USB C"],
        "USB-A": ["USB-A", "USB A", "USB 3.0 tipo A"],
        "VGA": ["VGA", "D-Sub", "VGA (D-SUB)"],
        "RJ45": ["RJ45", "RJ-45"],
        "C13": ["C13"],
        "C14": ["C14"],
    }[c])


# ---------------------------------------------------------------------------
# Constructores por categoría: devuelven (nombre, frases de la descripción)
# Cada frase es (atributo o None, texto). Las frases con atributo se pueden omitir.
# ---------------------------------------------------------------------------

def _cpu(s: dict, r: random.Random):
    a, e = s["atributos"], s.get("extra", {})
    nombre = r.choice(["", "Procesador ", "Micro ", "PROCESADOR "]) + s["nombre"]
    if r.random() < 0.3:
        nombre += f" {v_socket(a['socket'], r)}"
    frases = [
        ("socket", r.choice(["Socket {}", "Zócalo: {}", "Plataforma {}", "Compatible con mothers {}"])
         .format(v_socket(a["socket"], r))),
        ("nucleos", r.choice(["{n} núcleos y {h} hilos", "{n} Cores / {h} Threads", "{n}C/{h}T",
                              "Cantidad de núcleos: {n}"]).format(n=a["nucleos"], h=e["hilos"])),
        ("tdp_w", r.choice(["TDP {}", "TDP: {}", "Consumo térmico (TDP) de {}", "{} de TDP"])
         .format(v_w(a["tdp_w"], r))),
        (None, f"Frecuencia turbo hasta {_decimal(e['ghz'], r)} GHz"),
        (None, r.choice(["Caché L3 de 32 MB", "Caché L3 16MB", "Proceso de fabricación avanzado"])),
    ]
    if a["socket"] in ("AM4", "LGA1200"):
        frases.append((None, "Memoria soportada: DDR4-3200"))
    elif a["socket"] in ("AM5", "LGA1851"):
        frases.append((None, "Memoria soportada: DDR5-5600"))
    else:
        frases.append((None, "Compatible con memorias DDR4 y DDR5 según la placa"))
    if s["nombre"].endswith("F"):
        frases.append((None, "Sin gráficos integrados: requiere placa de video"))
    return nombre, frases


def _motherboard(s: dict, r: random.Random):
    a = s["atributos"]
    nombre = r.choice(["", "Mother ", "Motherboard ", "Placa Madre "]) + s["nombre"]
    if r.random() < 0.3:
        nombre += f" {v_socket(a['socket'], r)}"
    slots = 2 if a["formato"] == "Mini-ITX" else 4
    frases = [
        ("socket", r.choice(["Socket {}", "Zócalo {}", "Soporta procesadores {}"])
         .format(v_socket(a["socket"], r))),
        ("tipo_ram", r.choice(["Memoria {}", f"{slots} slots {{}} hasta 128GB", "Soporta memorias {}"])
         .format(v_ddr(a["tipo_ram"], r))),
        ("formato", r.choice(["Formato {}", "Factor de forma: {}", "Tamaño {}"])
         .format(v_formato(a["formato"], r))),
        (None, "Conector de alimentación ATX de 24 pines + 8 pines EPS"),
        (None, r.choice(["Slot M.2 PCIe 4.0", "1x M.2 NVMe", "2 slots M.2"])),
        (None, r.choice(["Audio HD 7.1", "LAN Gigabit", "WiFi 6 + Bluetooth"])),
    ]
    return nombre, frases


def _ram(s: dict, r: random.Random):
    a, e = s["atributos"], s.get("extra", {})
    kit = e.get("kit")
    if kit:
        cap_texto = r.choice([f"Kit {kit[0]}x{kit[1]}GB", f"{a['capacidad_gb']}GB ({kit[0]}x{kit[1]}GB)",
                              f"Kit {a['capacidad_gb']}GB ({kit[0]} x {kit[1]} GB)"])
    else:
        cap_texto = v_gb(a["capacidad_gb"], r)
    nombre = r.choice(["Memoria ", "Memoria RAM ", "RAM ", ""]) + s["nombre"]
    if r.random() < 0.85:
        nombre += f" {cap_texto}"
    if r.random() < 0.8:
        nombre += f" {v_ddr(a['tipo'], r)}"
    if r.random() < 0.6:
        nombre += f" {a['frecuencia_mhz']}"
    frases = [
        ("tipo", r.choice(["Tipo: {}", "Memoria {}", "Tecnología {}"]).format(v_ddr(a["tipo"], r))),
        ("capacidad_gb", r.choice(["Capacidad: {}", "{} de capacidad"]).format(cap_texto)),
        ("frecuencia_mhz", r.choice(["Velocidad {}", "Frecuencia: {}"])
         .format(v_frecuencia(a["frecuencia_mhz"], a["tipo"], r))),
        (None, r.choice(["Voltaje 1.35V", "Voltaje 1,2V", "Voltaje 1.1V"])),
        (None, r.choice(["Latencia CL16", "Latencia CL18", "CL36"])),
        (None, "Compatible con Intel XMP 3.0 y AMD EXPO"),
    ]
    return nombre, frases


def _gpu(s: dict, r: random.Random):
    a, e = s["atributos"], s.get("extra", {})
    nombre = r.choice(["Placa de Video ", "Tarjeta Gráfica ", "", "VGA "]) + s["nombre"]
    if r.random() < 0.8:
        nombre += " " + r.choice([f"{a['vram_gb']}GB", f"{a['vram_gb']}G", f"{a['vram_gb']}GB {e['gddr']}"])
    largo = a["largo_mm"]
    frases = [
        ("vram_gb", r.choice(["Memoria {} " + e["gddr"], "{} de memoria " + e["gddr"], "VRAM: {}"])
         .format(v_gb(a["vram_gb"], r))),
        ("consumo_w", r.choice(["Consumo: {}", "TBP {}", "Consumo total de la placa {}",
                                "Potencia de la placa: {}"]).format(v_w(a["consumo_w"], r))),
        ("largo_mm", r.choice([
            f"Largo: {v_mm(largo, r)}", f"Longitud {v_mm(largo, r)}",
            f"Dimensiones: {largo} x {r.randint(105, 140)} x {r.choice([38, 40, 41, 50, 55])} mm",
        ])),
        (None, f"Fuente recomendada: {v_w(e['fuente_recomendada'], r)}"),
        (None, "Salidas: 1x HDMI 2.1, 3x DisplayPort 1.4a"),
        (None, f"{r.choice([2, 3])} ventiladores de {r.choice([90, 95, 100])} mm"),
    ]
    return nombre, frases


def _almacenamiento(s: dict, r: random.Random):
    a, e = s["atributos"], s.get("extra", {})
    tipo = a["tipo"]
    prefijos = {
        "NVMe": ["SSD M.2 NVMe ", "Disco Sólido NVMe ", "SSD "],
        "SSD SATA": ["Disco SSD ", "SSD ", "Disco Sólido "],
        "HDD": ["Disco Rígido ", "HDD ", "Disco Duro "],
    }[tipo]
    nombre = r.choice(prefijos) + s["nombre"]
    if r.random() < 0.85:
        nombre += f" {v_capacidad_disco(a['capacidad_gb'], r)}"
    if tipo == "NVMe":
        pcie = e["pcie"]
        frase_tipo = r.choice([f"Interfaz M.2 NVMe PCIe {pcie}", f"NVMe Gen{pcie[0]}",
                               "Formato M.2 2280 NVMe", f"PCIe {pcie} x4 NVMe"])
    elif tipo == "SSD SATA":
        frase_tipo = r.choice(["Interfaz SATA III", 'SSD 2,5" SATA 3', "SATA 6Gb/s"])
    else:
        frase_tipo = r.choice([f'Disco rígido 3.5" {e["rpm"]} RPM', f"HDD SATA {e['rpm']}rpm",
                               "Disco mecánico de 3,5 pulgadas"])
    frases = [
        ("tipo", frase_tipo),
        ("capacidad_gb", r.choice(["Capacidad: {}", "{}", "Almacenamiento de {}"])
         .format(v_capacidad_disco(a["capacidad_gb"], r))),
        (None, f"Lectura hasta {e.get('lectura', 200)} MB/s"),
        (None, "Caché 256MB" if tipo == "HDD" else "Resistencia: 600 TBW"),
    ]
    return nombre, frases


def _fuente(s: dict, r: random.Random):
    a, e = s["atributos"], s.get("extra", {})
    nombre = r.choice(["Fuente ", "Fuente de Alimentación ", "FUENTE ", "PSU "]) + s["nombre"]
    if r.random() < 0.75:
        nombre += f" {v_w(a['potencia_w'], r)}"
    if r.random() < 0.4 and a["certificacion"] != "Sin certificación":
        nombre += f" {v_certificacion(a['certificacion'], r)}"
    frases = [
        ("potencia_w", r.choice(["Potencia: {}", "{} reales", "Potencia nominal {}"])
         .format(v_w(a["potencia_w"], r))),
        ("certificacion", r.choice(["Certificación {}", "{}", "Eficiencia {}"])
         .format(v_certificacion(a["certificacion"], r))),
        (None, "Ventilador de 120mm silencioso"),
        (None, "Conectores: 1x 24 pines, 2x PCIe 6+2"),
        (None, "Entrada 220V, PFC activo"),
    ]
    if "pico" in e:
        frases.append((None, f"Potencia pico {v_w(e['pico'], r)}"))
    return nombre, frases


def _gabinete(s: dict, r: random.Random):
    a, e = s["atributos"], s.get("extra", {})
    nombre = r.choice(["Gabinete ", "GABINETE ", "Case ", ""]) + s["nombre"].removeprefix("Gabinete ")
    maximo = a["formatos_admitidos"][0]
    frase_formato = r.choice({
        "E-ATX": ["Soporta mothers E-ATX / ATX / Micro-ATX / Mini-ITX", "Compatibilidad: E-ATX, ATX, mATX, ITX",
                  "Admite placas hasta E-ATX"],
        "ATX": ["Soporta mothers ATX / Micro-ATX / Mini-ITX", "Compatibilidad: ATX, mATX, ITX",
                "Gabinete ATX Mid Tower", "Formato ATX"],
        "Micro-ATX": ["Soporta Micro-ATX y Mini-ITX", "Formato Micro ATX", "Compatible mATX / ITX",
                      "Mini torre mATX"],
        "Mini-ITX": ["Solo Mini-ITX", "Formato Mini ITX", "Compatible con placas ITX"],
    }[maximo])
    frases = [("formatos_admitidos", frase_formato)]
    if a["largo_max_gpu_mm"] is not None:
        frases.append(("largo_max_gpu_mm", r.choice([
            "Soporta placas de video de hasta {}", "Largo máximo de GPU: {}", "VGA hasta {}",
            "Espacio para GPU: {}"]).format(v_mm(a["largo_max_gpu_mm"], r))))
    if "fuente_incluida" in e:
        frases.append((None, f"Incluye fuente de {v_w(e['fuente_incluida'], r)}"))
    elif maximo == "Mini-ITX":
        frases.append((None, "Soporta fuente SFX"))
    else:
        frases.append((None, "Soporta fuente ATX (no incluida)"))
    frases += [
        (None, f"Soporta coolers de CPU de hasta {r.choice([155, 160, 165])} mm"),
        (None, f"Incluye {r.choice([2, 3, 4])} ventiladores de 120 mm"),
        (None, "Panel lateral de vidrio templado"),
    ]
    return nombre, frases


def _cooler(s: dict, r: random.Random):
    a, e = s["atributos"], s.get("extra", {})
    es_liquida = "radiador" in e
    prefijos = ["Refrigeración Líquida ", "Water Cooling "] if es_liquida else \
        ["Cooler ", "Cooler CPU ", "Disipador ", ""]
    nombre = r.choice(prefijos) + s["nombre"].removeprefix("Cooler ")
    intel = [x[3:] for x in a["sockets"] if x.startswith("LGA")]
    amd = [x for x in a["sockets"] if x.startswith("AM")]
    partes_estilo1 = ([f"Intel LGA{'/'.join(intel)}"] if intel else []) + \
        ([f"AMD {'/'.join(amd)}"] if amd else [])
    partes_estilo3 = ([f"Intel LGA {' / '.join(intel)}"] if intel else []) + \
        ([f"AMD {' / '.join(amd)}"] if amd else [])
    frase_sockets = r.choice([
        "Compatible con: " + ", ".join(partes_estilo1),
        "Sockets: " + ", ".join(a["sockets"]),
        "Soporta " + " y ".join(partes_estilo3),
    ])
    frases = [("sockets", frase_sockets)]
    if a["altura_mm"] is not None:
        frases.append(("altura_mm", r.choice(["Altura: {}", "Alto {}", "Altura total {}"])
                       .format(v_mm(a["altura_mm"], r))))
    frases += [
        (None, "Ventilador de 120 mm PWM" if not es_liquida else f"Radiador de {e['radiador']} mm"),
        (None, f"TDP soportado {r.choice([180, 200, 220, 250])}W"),
        (None, r.choice(["Pasta térmica incluida", "Iluminación ARGB"])),
    ]
    return nombre, frases


def _ups(s: dict, r: random.Random):
    a = s["atributos"]
    nombre = r.choice(["UPS ", "Ups ", ""]) + s["nombre"]
    if r.random() < 0.8:
        nombre += r.choice([f" {a['va']}VA", f" {a['va']} VA"])
    if r.random() < 0.4:
        nombre += f" {a['w']}W"
    frases = [
        ("va", r.choice(["Potencia: {}VA", "{} VA", "Capacidad {}va"]).format(a["va"])),
        ("w", r.choice(["{}W", "{} W reales", "Potencia activa {} watts"]).format(a["w"])),
    ]
    if a["autonomia_minutos"] is not None:
        frases.append(("autonomia_minutos", r.choice([
            "Autonomía: {} min", "Autonomía aprox. {} minutos a media carga", "Respaldo de {} min"])
            .format(a["autonomia_minutos"])))
    frases += [
        (None, "Recarga completa en 6 a 8 horas"),
        (None, f"{r.choice([3, 4, 6])} tomas de 220V"),
        (None, r.choice(["Batería 12V 7Ah", "Batería 12V 9Ah"])),
        (None, "Ideal para PC de escritorio + monitor"),
    ]
    return nombre, frases


def _cables(s: dict, r: random.Random):
    a = s["atributos"]
    nombre = "Cable " + s["nombre"].removeprefix("Cable ")
    if r.random() < 0.6:
        nombre += f" {v_largo_m(a['largo_m'], r)}"
    ca, cb = a["conector_a"], a["conector_b"]
    if ca == cb == "RJ45":
        frase_conectores = r.choice(["Fichas RJ45 en ambos extremos", "RJ-45 a RJ-45"])
    elif ca == cb:
        x = v_conector(ca, r)
        frase_conectores = r.choice([f"Conectores {x} a {x}", f"{x} macho a {x} macho", f"{x} - {x}"])
    else:
        frase_conectores = r.choice(["Conectores {} a {}", "{} macho a {} macho", "{} - {}"]) \
            .format(v_conector(ca, r), v_conector(cb, r))
    frases = [
        ("conectores", frase_conectores),
        ("largo_m", r.choice(["Largo: {}", "Longitud {}", "{} de largo", "Medida: {}"])
         .format(v_largo_m(a["largo_m"], r))),
    ]
    if "HDMI" in (ca, cb):
        frases.append((None, r.choice(["Soporta 4K a 60Hz y HDR", "Versión 2.1, 48 Gbps"])))
    if ca == "USB-C" and cb in ("HDMI", "DisplayPort"):
        frases.append((None, "Requiere puerto USB-C con soporte DP Alt Mode"))
    if ca == cb == "USB-C":
        frases.append((None, "Carga rápida hasta 100W"))
    if ca == cb == "RJ45":
        frases.append((None, "Categoría 6, hasta 1 Gbps"))
    if "C13" in (ca, cb):
        frases.append((None, "Ideal para conectar la PC a la UPS"))
    return nombre, frases


CONSTRUCTORES = {
    "cpu": _cpu, "motherboard": _motherboard, "ram": _ram, "gpu": _gpu,
    "almacenamiento": _almacenamiento, "fuente": _fuente, "gabinete": _gabinete,
    "cooler": _cooler, "ups": _ups, "cables": _cables,
}


def _declarados(categoria: str, s: dict) -> dict:
    """Atributos que la fuente entrega como dato estructurado, no como texto.

    Son los que escribe `semillas.yaml` en `declarados` más los que se deducen de la semilla.
    Es el mismo camino por el que entrarían los datos técnicos si la API de la tienda los expone.
    """
    a, e = s["atributos"], s.get("extra", {})
    declarados = dict(s.get("declarados", {}))
    if categoria == "ram":
        declarados.setdefault("modulos", e["kit"][0] if "kit" in e else 1)
        declarados.setdefault("formato_modulo", "DIMM")
    elif categoria == "gpu" and "fuente_recomendada" in e:
        declarados.setdefault("fuente_recomendada_w", e["fuente_recomendada"])
    elif categoria == "almacenamiento":
        declarados.setdefault("conexion", "M.2" if a["tipo"] in ("NVMe", "M.2 SATA") else "SATA")
    elif categoria == "gabinete":
        declarados.setdefault("incluye_fuente", "si" if "fuente_incluida" in e else "no")
        if "fuente_incluida" in e:
            declarados.setdefault("potencia_fuente_w", e["fuente_incluida"])
    return declarados


def _envolver_html(frases: list[str], r: random.Random) -> str:
    estilo = r.choice(["br", "p", "lista", "plano", "plano"])
    if estilo == "br":
        return "<br>".join(frases)
    if estilo == "p":
        return "".join(f"<p>{f}</p>" for f in frases)
    if estilo == "lista":
        return "<ul>" + "".join(f"<li>{f}&nbsp;</li>" for f in frases) + "</ul>"
    return ". ".join(f.rstrip(".") for f in frases) + "."


def generar(semillas: dict, semilla: int = SEMILLA) -> tuple[list[ProductoCrudo], dict]:
    r = random.Random(semilla)
    productos, etiquetas = [], {}
    for categoria, lista in semillas.items():
        for i, s in enumerate(lista, start=1):
            codigo = f"{PREFIJO_CODIGO[categoria]}{i:03d}"
            nombre, frases = CONSTRUCTORES[categoria](s, r)
            omitidos, textos = [], []
            for atributo, texto in frases:
                if atributo and r.random() < P_OMITIR:
                    omitidos.append(atributo)
                    continue
                textos.append(texto)
            r.shuffle(textos)
            textos += r.sample(TEXTO_COMERCIAL, k=r.randint(0, 2))
            if r.random() < 0.15:
                nombre = nombre.upper()
            marca = s.get("marca")
            if marca and r.random() < 0.15:
                marca = marca.upper()
            categoria_origen = r.choice(CATEGORIA_ORIGEN[categoria]).format(
                marca=marca or "", tipo=s["atributos"].get("tipo", "")).strip()
            stock = r.choices([0, r.randint(1, 3), r.randint(4, 25)], weights=[2, 3, 5])[0]
            productos.append(ProductoCrudo(
                codigo=codigo, nombre=nombre, descripcion=_envolver_html(textos, r),
                categoria=categoria_origen, marca=marca, precio=float(s["precio"]), stock=stock,
                atributos_declarados=_declarados(categoria, s),
            ))
            etiquetas[codigo] = {"categoria": categoria, "atributos": s["atributos"], "omitidos": omitidos}
    return productos, etiquetas


def main() -> None:
    semillas = yaml.safe_load((DIR_CATALOGO_PRUEBA / "semillas.yaml").read_text(encoding="utf-8"))
    productos, etiquetas = generar(semillas)
    (DIR_CATALOGO_PRUEBA / "productos_crudos.json").write_text(
        json.dumps([p.model_dump() for p in productos], ensure_ascii=False, indent=1), encoding="utf-8")
    (DIR_CATALOGO_PRUEBA / "etiquetas.json").write_text(
        json.dumps(etiquetas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Generados {len(productos)} productos en {DIR_CATALOGO_PRUEBA}")


if __name__ == "__main__":
    main()
