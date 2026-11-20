"""Test de contrato: el examen que tiene que aprobar cualquier fuente para entrar al sistema.

La fuente API se prueba acá con respuestas simuladas (sin red). Contra la API real se corre a pedido,
porque baja todo el catálogo: AMN_PROBAR_API=1 uv run pytest tests/test_contrato_fuente.py
(necesita AMN_API_URL y la sesión en AMN_API_TOKEN o AMN_API_COOKIE; ver .env.example).
"""

import os

import pytest

from mcp_tienda.ingesta.fuentes import FuenteAPI, FuenteCSV, FuentePrueba, obtener_fuente
from mcp_tienda.ingesta.fuentes.api import ErrorFuenteAPI
from mcp_tienda.ingesta.fuentes.export_csv import parsear_precio
from mcp_tienda.modelos import ProductoCrudo

CSV_EJEMPLO = """Código;Producto;Detalle;Rubro;Marca;Precio;Stock
P-1001;Fuente Corsair CV650;650W 80 Plus Bronze;Fuentes;Corsair;$ 89.000,00;5
P-1002;Cable HDMI 2 m;HDMI macho a HDMI macho;Cables;Netmak;6.500;0
"""


def _fuente_csv(tmp_path):
    ruta = tmp_path / "export.csv"
    ruta.write_text(CSV_EJEMPLO, encoding="utf-8")
    columnas = {"codigo": "Código", "nombre": "Producto", "descripcion": "Detalle", "categoria": "Rubro",
                "marca": "Marca", "precio": "Precio", "stock": "Stock"}
    return FuenteCSV(ruta, columnas=columnas, separador=";")


def _fuentes(tmp_path):
    fuentes = [FuentePrueba(), _fuente_csv(tmp_path)]
    if os.getenv("AMN_PROBAR_API") == "1":
        fuentes.append(obtener_fuente("api"))
    return fuentes


@pytest.fixture(params=["prueba", "csv", "api"])
def fuente(request, tmp_path):
    if request.param == "api" and os.getenv("AMN_PROBAR_API") != "1":
        pytest.skip("Contra la API real solo se prueba a pedido: AMN_PROBAR_API=1")
    return {f.nombre: f for f in _fuentes(tmp_path)}[request.param]


def test_contrato(fuente):
    productos = list(fuente.iterar_productos())
    assert productos, "la fuente no devolvió productos"
    assert all(isinstance(p, ProductoCrudo) for p in productos)
    codigos = [p.codigo for p in productos]
    assert len(codigos) == len(set(codigos)), "hay códigos repetidos"
    assert all(p.precio > 0 and p.stock >= 0 and p.nombre.strip() for p in productos)
    assert all(p.categoria.strip() for p in productos), "todo producto necesita categoría de origen"


def test_csv_mapea_columnas(tmp_path):
    productos = list(_fuente_csv(tmp_path).iterar_productos())
    assert productos[0].precio == 89000.0 and productos[0].stock == 5
    assert productos[1].precio == 6500.0 and productos[1].categoria == "Cables"


@pytest.mark.parametrize("texto, esperado", [
    ("$ 145.000,50", 145000.5), ("145000", 145000.0), ("145.000", 145000.0), ("145,5", 145.5),
    ("1.234.567", 1234567.0),
])
def test_parsear_precio_argentino(texto, esperado):
    assert parsear_precio(texto) == esperado


# --- Fuente API, con respuestas simuladas -------------------------------------------------------

def _item(sku, precio=1500.0, stock=3):
    return {"product": {"sku": sku, "name": f"CPU AMD RYZEN 5 {sku}".ljust(37) + "AM4", "desc": "65w", "hdesc": "nota",
                        "category": {"code": "333", "name": "Microprocesadores (CPU)"}, "brand": {"name": "AMD"},
                        "imageUrl": f"https://ejemplo.invalid/{sku}.jpg"},
            "inventory": {"totalQty": stock}, "pinpesos": precio}


def _api_simulada(paginas, con_sesion=True):
    """Devuelve (función pedir, lista de pedidos recibidos)."""
    pedidos = []

    def pedir(ruta, parametros):
        pedidos.append((ruta, parametros))
        numero = parametros["page"]
        return {"data": paginas[numero - 1], "pricesVisible": con_sesion,
                "pagination": {"hasNextPage": numero < len(paginas)}}

    return pedir, pedidos


def test_fuente_api_recorre_las_paginas_y_mapea():
    paginas = [[_item("A1"), _item("A2", stock=-2)], [_item("A2"), _item("A3", precio=None)]]
    pedir, pedidos = _api_simulada(paginas)
    fuente = FuenteAPI("https://ejemplo.invalid/api", cookie="sesion=x", pedir=pedir)
    productos = list(fuente.iterar_productos())
    assert [p.codigo for p in productos] == ["A1", "A2"]          # A2 repetido se ignora; A3 no tiene precio
    assert fuente.sin_precio == 1 and [p["page"] for _, p in pedidos] == [1, 2]
    a2 = productos[1]
    assert a2.stock == 0                                          # el stock negativo se toma como 0
    assert (a2.categoria_codigo, a2.descripcion_interna, a2.marca) == ("333", "nota", "AMD")
    assert a2.precio == 1500.0 and a2.categoria == "Microprocesadores (CPU)"


def test_fuente_api_sin_sesion_explica_que_falta_la_cookie():
    pedir, _ = _api_simulada([[_item("A1", precio=None)]], con_sesion=False)
    with pytest.raises(ErrorFuenteAPI, match="AMN_API_TOKEN"):
        list(FuenteAPI("https://ejemplo.invalid/api", pedir=pedir).iterar_productos())


def test_fuente_api_items_crudos_no_necesitan_sesion():
    pedir, _ = _api_simulada([[_item("A1", precio=None)], [_item("A1"), _item("A2", precio=None)]], con_sesion=False)
    items = list(FuenteAPI("https://ejemplo.invalid/api", pedir=pedir).iterar_items())
    assert [i["product"]["sku"] for i in items] == ["A1", "A2"]
