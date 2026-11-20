import pytest

from mcp_tienda.catalogo import FiltroInvalido


def test_cuenta_por_categoria(catalogo):
    conteo = catalogo.contar_por_categoria()
    assert sum(conteo.values()) == 116
    assert conteo["cpu"] == 17 and conteo["ups"] == 8 and conteo["cables"] == 13


def test_obtener_producto(catalogo):
    p = catalogo.obtener("CAB002")
    assert p.categoria == "cables" and p.atributos["largo_m"] == 2.0
    assert catalogo.obtener("NOEXISTE") is None


def test_filtro_categoria_y_precio(catalogo):
    productos = catalogo.buscar(categoria="gpu", precio_max=400000, solo_con_stock=False, limite=50)
    assert productos and all(p.categoria == "gpu" and p.precio <= 400000 for p in productos)
    assert [p.precio for p in productos] == sorted(p.precio for p in productos)


def test_solo_con_stock(catalogo):
    con_stock = catalogo.buscar(categoria="ups", limite=50)
    todos = catalogo.buscar(categoria="ups", solo_con_stock=False, limite=50)
    assert all(p.stock > 0 for p in con_stock)
    assert len(todos) == 8 and len(con_stock) < len(todos)


def test_filtro_marca_sin_importar_mayusculas(catalogo):
    productos = catalogo.buscar(marca="corsair", solo_con_stock=False, limite=50)
    assert productos and all(p.marca.lower() == "corsair" for p in productos)


def test_filtro_atributo_igualdad_y_rango(catalogo):
    am4 = catalogo.buscar(categoria="motherboard", atributos={"socket": "am4"}, solo_con_stock=False, limite=50)
    assert len(am4) == 5 and all(p.atributos["socket"] == "AM4" for p in am4)
    fuertes = catalogo.buscar(categoria="fuente", atributos={"potencia_w__min": 750}, solo_con_stock=False)
    assert {p.codigo for p in fuertes} == {"FUE007", "FUE008", "FUE009", "FUE010"}


def test_filtro_atributo_lista_significa_contiene(catalogo):
    gabinetes = catalogo.buscar(categoria="gabinete", atributos={"formatos_admitidos": "Mini-ITX"},
                                solo_con_stock=False, limite=50)
    assert gabinetes and all("Mini-ITX" in p.atributos["formatos_admitidos"] for p in gabinetes)
    # Los que no aparecen son los que no informan formatos: sin datos no se los ofrece.
    encontrados = {p.codigo for p in gabinetes}
    resto = [p for p in catalogo.buscar(categoria="gabinete", solo_con_stock=False, limite=50)
             if p.codigo not in encontrados]
    assert all(p.atributos["formatos_admitidos"] is None for p in resto)


def test_filtro_decimal(catalogo):
    productos = catalogo.buscar(categoria="cables", atributos={"conector_a": "HDMI", "largo_m": 2})
    assert [p.codigo for p in productos] == ["CAB002"]


def test_atributo_inexistente_da_error(catalogo):
    with pytest.raises(FiltroInvalido):
        catalogo.buscar(categoria="cpu", atributos={"color": "rojo"})
    with pytest.raises(FiltroInvalido):
        catalogo.buscar(categoria="cpu", atributos={"socket__mayor": "x"})


def test_texto_sin_tildes_y_con_plural(catalogo):
    nombres = [p.nombre.lower() for p in catalogo.buscar(texto="rtx 4060", categoria="gpu")]
    assert "4060" in nombres[0]
    assert all(p.categoria == "ups" for p in catalogo.buscar(texto="UPS", categoria="ups"))
    assert catalogo.buscar(texto="cables hdmi")  # «cables» → prefijo «cable»


def test_texto_raro_no_rompe_fts(catalogo):
    # Comillas, operadores de FTS5 y SQL no tienen que romper la consulta ni la base.
    for texto in ['"; DROP TABLE productos; --', "AND OR NOT NEAR", "*", "¿?¡!", "cable \"hdmi"]:
        assert isinstance(catalogo.buscar(texto=texto), list)
    assert catalogo.obtener("CAB002") is not None
