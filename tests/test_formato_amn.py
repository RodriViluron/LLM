"""Lector del formato del catálogo real de la tienda, probado con productos reales.

`tests/datos/muestra_amn.json` son 53 productos bajados de la API pública (solo los campos que usa
el lector). Cada test fija un caso que 3PC.PRG lee mal o que el lector tiene que resolver bien.
"""

import json
from pathlib import Path

import pytest

from evaluacion.calidad_catalogo import analizar
from mcp_tienda.ingesta import formato_amn
from mcp_tienda.ingesta.cargar import procesar
from mcp_tienda.ingesta.formato_amn import CONTRADICCION, FORMATO_PRG, ILEGIBLE, leer, renglones
from mcp_tienda.modelos import ProductoCrudoAMN

MUESTRA = json.loads((Path(__file__).parent / "datos" / "muestra_amn.json").read_text(encoding="utf-8"))
POR_SKU = {item["product"]["sku"]: item["product"] for item in MUESTRA}


def lectura(sku: str) -> formato_amn.Lectura:
    p = POR_SKU[sku]
    return leer(p["name"], p["desc"], p["hdesc"], p["category"]["code"])


def clases(lec: formato_amn.Lectura, atributo: str) -> set[str]:
    return {a.clase for a in lec.avisos if a.atributo == atributo}


# --- Renglones y categorías -------------------------------------------------------------------

def test_renglones_de_50_columnas():
    # En el catálogo «**SIN COOLER» termina justo en la columna 50 y sigue «NUCLEOS» pegado.
    desc = POR_SKU["R7700X"]["desc"]
    assert "**SIN COOLERNUCLEOS" in desc
    assert renglones(desc)[0].endswith("**SIN COOLER") and renglones(desc)[1].startswith("NUCLEOS: 8")


@pytest.mark.parametrize("sku, categoria", [
    ("12400F", "cpu"), ("Z590-P", "motherboard"), ("KV1632", "ram"), ("2F5050", "gpu"), ("M2RE4T", "almacenamiento"),
    ("WDRE2T", "almacenamiento"), ("GAFTTG", "gabinete"), ("GF1000", "fuente"), ("AS600W", "cooler"),
    ("F495DE", None),   # fuente redundante de servidor: está en «Fuentes» pero no es «FTE PC»
    ("CAH212", None),   # cable HDMI
])
def test_clasifica_como_el_prg(sku, categoria):
    assert lectura(sku).categoria == categoria


# --- CPU --------------------------------------------------------------------------------------

def test_cpu_intel_completa():
    a = lectura("12400F").atributos
    assert a == {"socket": "LGA1700", "nucleos": 6, "tdp_w": 65, "generacion": "12", "consumo_max_w": 117,
                 "incluye_cooler": "si", "video_integrado": "no"}


def test_cpu_sin_video_escrito_con_un_espacio():
    # «** SIN VIDEO»: 3PC.PRG no lo encuentra, cree que tiene video y deja armar una PC sin placa de video.
    lec = lectura("3600XT")
    assert lec.atributos["video_integrado"] == "no"
    assert clases(lec, "video_integrado") == {FORMATO_PRG}


def test_cpu_sin_cooler_y_consumo_maximo():
    a = lectura("U7265K").atributos
    assert a["incluye_cooler"] == "no" and (a["tdp_w"], a["consumo_max_w"]) == (125, 250)


@pytest.mark.parametrize("sku, nucleos", [("RY3200", 4), ("CU9285", 24), ("R7700X", 8)])
def test_cpu_nucleos(sku, nucleos):
    # «12 (CPU 4 + GPU 8)» son 4; «8P+ 16E» son 24; el renglón de la GPU integrada también dice NUCLEOS.
    assert lectura(sku).atributos["nucleos"] == nucleos


def test_cpu_consumo_en_hdesc():
    assert lectura("IG5900").atributos["tdp_w"] == 58


def test_cpu_de_plataforma_vieja_queda_fuera_sin_avisos():
    # El socket viejo se guarda (valores_fuera_del_armado): así las reglas dicen «no cumple» y no «sin datos».
    lec = lectura("CE6550")
    assert lec.atributos["socket"] == "LGA775" and "LGA775" in lec.fuera_del_armado and lec.avisos == []


def test_cpu_contradiccion_entre_nombre_y_descripcion():
    p = POR_SKU["12400F"]
    lec = leer(p["name"], p["desc"].replace("**SIN VIDEO", "           "), p["hdesc"], "333")
    assert lec.atributos["video_integrado"] is None and clases(lec, "video_integrado") == {CONTRADICCION}


# --- Placa madre ------------------------------------------------------------------------------

def test_placa_intel_completa():
    assert lectura("Z590-P").atributos == {
        "socket": "LGA1200", "tipo_ram": "DDR4", "formato": "ATX", "generaciones": ["10", "11"],
        "ranuras_ram": 4, "puertos_sata": 4, "ranuras_m2": 3}


def test_placa_amd_generaciones_del_renglon_del_chipset():
    # El renglón de PCIe dice «*PCIe 4.0 (3ra GEN)»: esa es la generación de PCIe, no la de la CPU.
    assert lectura("TUF550").atributos["generaciones"] == ["2", "3"]
    assert lectura("A52DV2").atributos["generaciones"] == ["1", "2", "3"]


def test_placa_m2_sata_pcie_no_se_cuenta_como_puerto_sata():
    a = lectura("H610D5").atributos   # «-4 SATA3 -1 GLAN -1 M.2 SATA/PCIe»
    assert (a["puertos_sata"], a["ranuras_m2"]) == (4, 1)


def test_placa_sin_m2_tiene_cero_ranuras():
    assert lectura("GA41MT").atributos["ranuras_m2"] == 0


def test_generacion_de_cpu_y_placa_se_pueden_comparar():
    cpu, placa = lectura("12400F").atributos, lectura("61S2H2").atributos
    assert cpu["socket"] == placa["socket"] and cpu["generacion"] in placa["generaciones"]


# --- Cooler -----------------------------------------------------------------------------------

def test_cooler_sockets_solo_del_renglon_socket():
    assert set(lectura("AS600W").atributos["sockets"]) == {"LGA1200", "LGA1700", "LGA1851", "AM4", "AM5"}
    assert lectura("AS600W").atributos["potencia_enfriamiento_w"] == 265


def test_cooler_las_rpm_no_son_un_socket():
    # «VELOCIDAD: 1200 A 1800rpm» y la lista de sockets no trae el 1200: 3PC.PRG lo da por compatible.
    lec = lectura("CP0587")
    assert lec.atributos["sockets"] is None and clases(lec, "sockets") == {FORMATO_PRG}


def test_cooler_sin_potencia_queda_sin_datos():
    lec = lectura("TRL240")
    assert lec.atributos["potencia_enfriamiento_w"] is None and ILEGIBLE in clases(lec, "potencia_enfriamiento_w")
    assert lec.atributos["sockets"] == ["LGA1200"]   # la lista usa comas en vez de barras


# --- RAM --------------------------------------------------------------------------------------

def test_ram_kit():
    a = lectura("T16440").atributos
    assert (a["capacidad_gb"], a["modulos"], a["tipo"], a["formato_modulo"]) == (16, 2, "DDR4", "DIMM")


def test_ram_con_un_solo_espacio_antes_de_ddr():
    lec = lectura("A42400")   # 3PC.PRG exige dos espacios y no la ofrece
    assert lec.atributos["tipo"] == "DDR4" and clases(lec, "tipo") == {FORMATO_PRG}


@pytest.mark.parametrize("sku, motivo", [("4GSO17", "DDR3"), ("16DEL4", "ECC"), ("M2G800", "DDR2")])
def test_ram_que_no_es_de_pc_de_escritorio_queda_fuera(sku, motivo):
    assert motivo in lectura(sku).fuera_del_armado


# --- Placa de video, gabinete, fuente y discos ------------------------------------------------

def test_gpu():
    assert lectura("2F5050").atributos == {"vram_gb": 8, "fuente_recomendada_w": 550, "conectores_energia": "1x8pin",
                                           "consumo_w": None, "largo_mm": None}
    assert lectura("RX5808").atributos["fuente_recomendada_w"] == 500   # «FUENTE MIN.450W RECOMENDADA 500W»
    assert ILEGIBLE in clases(lectura("ARX550"), "fuente_recomendada_w")


def test_gabinete():
    sin_fuente, con_fuente = lectura("GAFTTG").atributos, lectura("6810CK").atributos
    assert sin_fuente["incluye_fuente"] == "no" and sin_fuente["formatos_admitidos"] == [
        "E-ATX", "ATX", "Micro-ATX", "Mini-ITX"]
    assert (con_fuente["incluye_fuente"], con_fuente["potencia_fuente_w"]) == ("si", 600)
    assert lectura("MESHBX").atributos["formatos_admitidos"] == ["ATX", "Micro-ATX", "Mini-ITX"]


def test_gabinete_rackeable_no_informa_formato():
    lec = lectura("S2U550")
    assert lec.atributos["formatos_admitidos"] is None and ILEGIBLE in clases(lec, "formatos_admitidos")


def test_fuente():
    assert lectura("GF1000").atributos == {"potencia_w": 1000, "certificacion": "80 Plus Gold", "conectores_pcie": 6}
    assert lectura("F55024").atributos == {"potencia_w": 550, "certificacion": None, "conectores_pcie": 0}


@pytest.mark.parametrize("sku, tipo, conexion, capacidad", [
    ("M2RE4T", "NVMe", "M.2", 4000), ("240GG3", "M.2 SATA", "M.2", 240),
    ("DC6048", "SSD SATA", "SATA", 480), ("WDRE2T", "HDD", "SATA", 2000),
])
def test_discos(sku, tipo, conexion, capacidad):
    assert lectura(sku).atributos == {"tipo": tipo, "conexion": conexion, "capacidad_gb": capacidad}


# --- Ingesta y reporte ------------------------------------------------------------------------

def _crudo(sku: str) -> ProductoCrudoAMN:
    p = POR_SKU[sku]
    return ProductoCrudoAMN(codigo=sku, nombre=p["name"], descripcion=p["desc"], descripcion_interna=p["hdesc"],
                            categoria=p["category"]["name"], categoria_codigo=p["category"]["code"],
                            precio=1000, stock=1)


def test_procesar_usa_el_lector_de_la_tienda():
    producto = procesar(_crudo("AS600W"))
    assert producto.categoria == "cooler" and "AM5" in producto.atributos["sockets"]
    # La descripción guardada es solo `desc`, con sus renglones; las notas de hdesc no se guardan.
    assert producto.descripcion.splitlines()[0].startswith("DIMENSION:") and "SOCKET" not in producto.descripcion


def test_procesar_no_mete_en_el_armado_lo_que_no_es_una_pieza():
    # Está en la categoría «Fuentes para PC y Servidores», pero es una fuente de servidor.
    assert procesar(_crudo("F495DE")).categoria == "otros"
    assert procesar(_crudo("CAH212")).categoria == "cables"


def test_reporte_de_calidad():
    r = analizar(MUESTRA)
    assert r["productos_leidos"] == len(MUESTRA) and r["piezas_de_pc"] == len(MUESTRA) - 2
    cpu = r["por_categoria"]["cpu"]
    assert cpu["fuera_del_armado"] == 1 and cpu["cobertura"]["tdp_w"]["con_dato"] == cpu["en_el_armado"]
    avisos = {(a["sku"], a["atributo"], a["clase"]) for a in r["avisos"]}
    assert {("3600XT", "video_integrado", FORMATO_PRG), ("CP0587", "sockets", FORMATO_PRG),
            ("A42400", "tipo", FORMATO_PRG)} <= avisos
    assert not any(a["sku"] in ("CE6550", "4GSO17") for a in r["avisos"])   # lo que queda fuera no genera avisos
