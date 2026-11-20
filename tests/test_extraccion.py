import json

import pytest
import yaml

from evaluacion.extraccion import evaluar
from mcp_tienda.config import DIR_CATALOGO_PRUEBA
from mcp_tienda.esquemas import cargar_esquemas, normalizar_categoria
from mcp_tienda.ingesta.extraccion import EXTRACTORES, extraer_atributos, limpiar_texto
from mcp_tienda.ingesta.generar_catalogo_prueba import generar


def con_dato(atributos: dict) -> dict:
    """Solo los atributos que se pudieron leer. Los esquemas también tienen atributos que hoy trae
    solo el catálogo real de la tienda (los lee formato_amn.py): en texto libre quedan en None."""
    return {clave: valor for clave, valor in atributos.items() if valor is not None}


def test_cada_atributo_del_esquema_tiene_extractor():
    for categoria, esquema in cargar_esquemas().items():
        assert categoria in EXTRACTORES, f"falta extractor para {categoria}"
        atributos = extraer_atributos(categoria, "", "")
        assert set(atributos) == set(esquema.atributos)


def test_limpiar_texto_saca_html_y_tildes():
    assert limpiar_texto("<p>Zócalo&nbsp;AM4</p><p>TDP 65W</p>") == "zocalo am4\ntdp 65w"


@pytest.mark.parametrize("texto, esperado", [
    ("Socket AM-4", "AM4"), ("sAM4", "AM4"), ("AM 5", "AM5"), ("FCLGA1700", "LGA1700"),
    ("Socket 1200", "LGA1200"), ("socket LGA-1851", "LGA1851"),
])
def test_socket_cpu_variantes(texto, esperado):
    assert extraer_atributos("cpu", "Procesador", texto)["socket"] == esperado


def test_socket_cpu_se_deduce_del_modelo():
    assert extraer_atributos("cpu", "AMD Ryzen 5 5600", "")["socket"] == "AM4"
    assert extraer_atributos("cpu", "Intel Core i5-13400F", "")["socket"] == "LGA1700"
    assert extraer_atributos("cpu", "Intel Core Ultra 5 245K", "")["socket"] == "LGA1851"


def test_nucleos_no_confunde_hilos():
    assert extraer_atributos("cpu", "x", "Hasta 12 hilos. 6C/12T")["nucleos"] == 6


def test_placa_ignora_conector_atx_de_24_pines():
    a = extraer_atributos("motherboard", "Mother Gigabyte B550 AORUS",
                          "Conector de alimentación ATX de 24 pines + 8 pines EPS")
    assert a["formato"] is None  # «ATX de 24 pines» es el conector, no el formato
    assert a["socket"] == "AM4"  # deducido del chipset


def test_placa_micro_atx_por_chipset_m():
    a = extraer_atributos("motherboard", "Gigabyte B550M DS3H", "Memoria DDR4")
    assert con_dato(a) == {"socket": "AM4", "tipo_ram": "DDR4", "formato": "Micro-ATX"}


def test_placa_ddr_d4_en_el_nombre():
    assert extraer_atributos("motherboard", "ASUS PRIME H610M-E D4", "")["tipo_ram"] == "DDR4"


def test_ram_kit_suma_capacidad():
    assert extraer_atributos("ram", "Corsair Vengeance Kit 2x16GB DDR5", "")["capacidad_gb"] == 32


def test_gpu_ignora_fuente_recomendada_y_pasa_cm_a_mm():
    a = extraer_atributos("gpu", "RTX 4060 8GB", "Fuente recomendada: 550W. Largo: 22,7 cm. TBP 115 W")
    assert con_dato(a) == {"vram_gb": 8, "consumo_w": 115, "largo_mm": 227}


def test_gpu_dimensiones():
    assert extraer_atributos("gpu", "x", "Dimensiones: 322 x 126 x 38 mm")["largo_mm"] == 322


def test_fuente_ignora_potencia_pico():
    a = extraer_atributos("fuente", "Fuente genérica", "500W reales. Potencia pico 600W. Sin certificación")
    assert con_dato(a) == {"potencia_w": 500, "certificacion": "Sin certificación"}


def test_fuente_sin_certificacion_80_plus_no_es_white():
    a = extraer_atributos("fuente", "Fuente 500W", "Sin certificación 80 Plus")
    assert a["certificacion"] == "Sin certificación"


def test_fuente_potencia_desde_modelo():
    assert con_dato(extraer_atributos("fuente", "Corsair RM750e", "Eficiencia 80+ Gold")) == {
        "potencia_w": 750, "certificacion": "80 Plus Gold"}


def test_gabinete_ignora_fuente_atx_y_expande_formatos():
    a = extraer_atributos("gabinete", "Gabinete Versa H18",
                          "Formato Micro ATX. Soporta fuente ATX (no incluida). VGA hasta 35 cm")
    assert con_dato(a) == {"formatos_admitidos": ["Micro-ATX", "Mini-ITX"], "largo_max_gpu_mm": 350}


def test_gabinete_no_confunde_cooler_con_gpu():
    a = extraer_atributos("gabinete", "Gabinete ATX", "Soporta coolers de CPU de hasta 165 mm")
    assert a["largo_max_gpu_mm"] is None


def test_ssd_sin_interfaz_es_sin_datos():
    assert extraer_atributos("almacenamiento", "SSD Kingston NV3 1TB", "")["tipo"] is None


def test_cooler_lista_de_sockets():
    a = extraer_atributos("cooler", "DeepCool AK400", "Compatible con: Intel LGA1700/1200, AMD AM5/AM4")
    assert set(a["sockets"]) == {"LGA1700", "LGA1200", "AM5", "AM4"}


def test_cable_ignora_dp_alt_mode():
    a = extraer_atributos("cables", "Cable USB-C a HDMI", "Requiere puerto USB-C con soporte DP Alt Mode. 180 cm")
    assert a == {"conector_a": "USB-C", "conector_b": "HDMI", "largo_m": 1.8}


def test_cable_un_solo_conector_es_igual_en_ambos_extremos():
    a = extraer_atributos("cables", "Cable HDMI 2.0", "Largo: 1,8 mts")
    assert a == {"conector_a": "HDMI", "conector_b": "HDMI", "largo_m": 1.8}


def test_valores_contradictorios_dan_sin_datos():
    assert extraer_atributos("cpu", "x", "Socket AM4. Socket LGA1700")["socket"] is None


def test_categorias_normalizadas():
    assert normalizar_categoria("Refrigeración CPU") == "cooler"
    assert normalizar_categoria("Micros AMD") == "cpu"
    assert normalizar_categoria("Mouse y Teclados") == "otros"


def test_catalogo_generado_esta_al_dia():
    """Si alguien toca semillas.yaml o el generador, hay que regenerar el JSON."""
    semillas = yaml.safe_load((DIR_CATALOGO_PRUEBA / "semillas.yaml").read_text(encoding="utf-8"))
    productos, etiquetas = generar(semillas)
    en_disco = json.loads((DIR_CATALOGO_PRUEBA / "productos_crudos.json").read_text(encoding="utf-8"))
    al_dia = [p.model_dump() for p in productos] == en_disco
    assert al_dia, "Corré: python -m mcp_tienda.ingesta.generar_catalogo_prueba"


def test_extraccion_sobre_catalogo_de_prueba():
    """Umbral mínimo y, sobre todo, cero valores erróneos (un erróneo puede dar un armado incompatible)."""
    productos = json.loads((DIR_CATALOGO_PRUEBA / "productos_crudos.json").read_text(encoding="utf-8"))
    etiquetas = json.loads((DIR_CATALOGO_PRUEBA / "etiquetas.json").read_text(encoding="utf-8"))
    r = evaluar(productos, etiquetas)
    assert r["exactitud_categoria"] == 1.0
    assert r["total"]["erroneos"] == 0, r["errores"]
    assert r["exactitud_total"] >= 0.85
