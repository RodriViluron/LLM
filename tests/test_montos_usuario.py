"""El monto que escribe el usuario se interpreta y se valida por código (paso 10, problema 31).

Dos partes: `interpretar_monto` pasa el texto a pesos (o avisa que no se entiende o está en dólares),
y `evaluar_presupuesto` lo compara con la escala de la tienda. El modelo no hace cuentas.
"""

import pytest

from mcp_tienda.armado.montos import evaluar_presupuesto, interpretar_monto

# Escala de la tienda con la forma que devuelve agente.escala_de_presupuesto (valores del reparto).
ESCALA = [
    {"gama": "baja", "tipico": 998_000, "desde": 919_000, "hasta": 1_119_000},
    {"gama": "media", "tipico": 2_762_000, "desde": 2_488_000, "hasta": 3_035_000},
    {"gama": "alta", "tipico": 5_320_000, "desde": 4_854_000, "hasta": 5_774_000},
    {"gama": "premium", "tipico": 8_800_000, "desde": 8_350_000, "hasta": 9_380_000},
]


@pytest.mark.parametrize("texto, monto", [
    ("$ 2.800.000", 2_800_000),
    ("2800000", 2_800_000),
    ("2,8 millones", 2_800_000),
    ("2 palos", 2_000_000),
    ("2,5 palos", 2_500_000),
    ("20 lucas", 20_000),
    ("20 mil pesos", 20_000),
    ("mil", 1_000),
    ("800k", 800_000),
    ("un palo", 1_000_000),
])
def test_montos_en_pesos_y_con_jerga(texto, monto):
    resultado = interpretar_monto(texto)
    assert resultado["moneda"] == "ARS" and resultado["monto"] == monto


@pytest.mark.parametrize("texto, monto", [
    ("dos millones", 2_000_000),          # antes daba 1.000.000: el número en palabras se ignoraba
    ("tres palos", 3_000_000),
    ("quinientas lucas", 500_000),
    ("un palo y medio", 1_500_000),
    ("1 millón y medio", 1_500_000),
    ("1 millon", 1_000_000),              # singular y sin tilde
    ("2,8M", 2_800_000),                  # «M» pegada al número es millones
    ("2.8 M", 2_800_000),
    ("tengo una idea: dos millones", 2_000_000),   # «una» no es el monto
])
def test_montos_en_palabras_medio_y_sufijo_m(texto, monto):
    resultado = interpretar_monto(texto)
    assert resultado["moneda"] == "ARS" and resultado["monto"] == monto


@pytest.mark.parametrize("texto, candidatos", [
    ("entre 1 y 2 millones", [1_000_000, 2_000_000]),
    ("1.500.000 o 2.000.000", [1_500_000, 2_000_000]),
])
def test_dos_montos_distintos_son_ambiguos(texto, candidatos):
    resultado = interpretar_monto(texto)
    assert resultado["monto"] is None and resultado["ambiguo"] and resultado["candidatos"] == candidatos


def test_el_mismo_monto_escrito_dos_veces_no_es_ambiguo():
    assert interpretar_monto("$ 2.800.000 (2,8 millones)")["monto"] == 2_800_000


@pytest.mark.parametrize("texto", ["u$s 1000", "1000 dólares", "USD 800", "tengo 500 usd"])
def test_los_dolares_no_se_convierten_sin_cotizacion(texto):
    resultado = interpretar_monto(texto)
    assert resultado["moneda"] == "USD" and resultado["monto"] is None
    assert "cotización" in resultado["motivo"]


def test_un_numero_chico_sin_unidad_es_ambiguo():
    resultado = interpretar_monto("20")
    assert resultado["monto"] is None and resultado["ambiguo"] is True
    assert resultado["candidatos"] == [20, 20_000]   # ¿20 pesos o 20 mil?


def test_un_texto_sin_monto_no_se_interpreta():
    assert interpretar_monto("tengo guita para una compu") is None


def test_monto_chico_no_alcanza_y_dice_el_minimo():
    resultado = evaluar_presupuesto(20_000, ESCALA)
    assert resultado["alcanza"] is False
    assert resultado["minimo"] == 919_000
    assert resultado["gama"] is None


def test_monto_que_alcanza_para_una_gama():
    resultado = evaluar_presupuesto(1_000_000, ESCALA)
    assert resultado["alcanza"] is True and resultado["gama"] == "baja"


def test_con_2_8_millones_entra_la_media():
    resultado = evaluar_presupuesto(2_800_000, ESCALA)
    assert resultado["gama"] == "media" and resultado["alcanza"] is True


def test_monto_sin_escala_no_inventa_una_respuesta():
    resultado = evaluar_presupuesto(1_000_000, [])
    assert resultado["alcanza"] is None and "referencia" in resultado["motivo"]
