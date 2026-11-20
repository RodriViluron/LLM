"""Paso 3: servidor MCP de la tienda y puente sincrónico.

Los tests levantan el servidor real (`python -m mcp_tienda.servidor`) por stdio, una sola vez,
sobre el catálogo de prueba temporal, y le hablan a través de mcp_tienda/cliente.py.
"""

import json

from langchain_core.messages import ToolMessage

from agente import crear_agente, eventos
from mcp_tienda.armado.candidatos import filtros_compatibles
from mcp_tienda.modelos import Producto
from tests.falsos import llamada, modelo_con, texto
from tools import Context, crear_tools

ARMADO = {"cpu": "CPU002", "motherboard": "MOT003", "ram": "RAM003", "gpu": "GPU003",
          "almacenamiento": "ALM003", "fuente": "FUE006", "gabinete": "GAB004"}


def test_el_servidor_expone_solo_las_tres_tools(cliente):
    nombres = sorted(t.name for t in cliente.tools())
    assert nombres == ["buscar_productos", "obtener_producto", "verificar_compatibilidad"]


def test_no_existe_ninguna_tool_para_confirmar(cliente):
    """El pedido lo confirma siempre el usuario: el agente no tiene con qué hacerlo."""
    for tool in crear_tools(cliente):
        assert "confirm" not in tool.name.lower(), tool.name
        assert "pedido" not in tool.name.lower(), tool.name


def test_buscar_productos_texto_corto_al_modelo_y_datos_completos_al_artifact(cliente):
    texto_modelo, datos = cliente.llamar("buscar_productos", categoria="cables",
                                         atributos={"conector_a": "HDMI", "largo_m": 2})
    para_el_modelo = json.loads(texto_modelo)
    assert [p["codigo"] for p in para_el_modelo["productos"]] == ["CAB002"]
    assert "descripcion" not in para_el_modelo["productos"][0]   # el modelo no carga con la descripción
    completo = datos["productos"][0]                              # la interfaz sí la recibe, sin HTML
    assert completo["codigo"] == "CAB002" and completo["descripcion"] and "<" not in completo["descripcion"]
    assert {"precio", "stock", "atributos", "imagen", "url"} <= set(completo)


def test_las_tools_son_sincronicas_y_devuelven_toolmessage_con_artifact(cliente):
    buscar = next(t for t in cliente.tools() if t.name == "buscar_productos")
    mensaje = buscar.invoke({"type": "tool_call", "id": "1", "name": "buscar_productos",
                             "args": {"categoria": "ups", "limite": 2}})
    assert isinstance(mensaje, ToolMessage)
    assert isinstance(mensaje.content, str) and json.loads(mensaje.content)["cantidad"] == 2
    assert len(mensaje.artifact["productos"]) == 2


def test_obtener_producto(cliente):
    resumen, datos = cliente.llamar_json("obtener_producto", codigo="GPU003")
    assert resumen["codigo"] == "GPU003" and "<" not in resumen["descripcion_texto_externo"]
    assert datos["producto"]["precio"] == resumen["precio"]


def test_los_errores_vuelven_como_dato(cliente):
    assert "error" in cliente.llamar_json("obtener_producto", codigo="NOEXISTE")[0]
    assert "error" in cliente.llamar_json("buscar_productos", categoria="cpu", atributos={"color": "rojo"})[0]
    assert "error" in cliente.llamar_json("verificar_compatibilidad", cpu="GPU001")[0]
    assert "error" in cliente.llamar_json("buscar_productos", compatible_con={"cpu": "CPU002"})[0]


def test_un_argumento_invalido_no_corta_el_turno(cliente):
    """Pasó con qwen3:4b: pidió categoria="placa de video" y el turno terminaba en una excepción."""
    buscar = next(t for t in cliente.tools() if t.name == "buscar_productos")
    mensaje = buscar.invoke({"type": "tool_call", "id": "1", "name": "buscar_productos",
                             "args": {"categoria": "placa de video"}})
    assert isinstance(mensaje, ToolMessage) and mensaje.status == "error"
    assert "gpu" in mensaje.content   # el modelo ve las categorías válidas y puede corregir la llamada


def test_verificar_compatibilidad_y_total_los_calcula_el_servidor(cliente, catalogo):
    reporte, datos = cliente.llamar_json("verificar_compatibilidad", **ARMADO)
    assert reporte["estado_general"] == "compatible"
    assert reporte["total"] == sum(catalogo.obtener(c).precio for c in ARMADO.values())
    assert set(datos["componentes"]) == set(ARMADO)


def test_avisa_cuantos_productos_quedaron_afuera_por_no_informar_el_dato(cliente, catalogo):
    """«Sin datos no hay afirmación»: un CPU que no dice sus núcleos no aparece, pero se avisa."""
    respuesta, _ = cliente.llamar_json("buscar_productos", categoria="cpu", atributos={"nucleos": 8},
                                       solo_con_stock=False, limite=20)
    cpus = catalogo.buscar(categoria="cpu", solo_con_stock=False, limite=50)
    sin_nucleos = [p for p in cpus if p.atributos["nucleos"] is None]
    assert sin_nucleos, "el catálogo de prueba tiene CPU sin el dato de núcleos"
    assert respuesta["sin_dato"] == len(sin_nucleos)
    assert all(p["atributos"]["nucleos"] == 8 for p in respuesta["productos"])
    assert "no informan" in respuesta["notas"][-1]


def test_compatible_con_devuelve_solo_candidatos_que_encajan(cliente, catalogo):
    elegido = {"cpu": "CPU002", "ram": "RAM003", "gabinete": "GAB005"}   # AM4, DDR4, gabinete Mini-ITX
    respuesta, datos = cliente.llamar_json("buscar_productos", categoria="motherboard", compatible_con=elegido,
                                           solo_con_stock=False, limite=20)
    assert datos["filtros_aplicados"] == {"socket": "AM4", "generaciones": "3", "tipo_ram": "DDR4",
                                          "formato__en": ["Mini-ITX"], "ranuras_ram__min": 1,
                                          "socket__en": ["AM4", "AM5", "LGA1200", "LGA1700", "LGA1851"]}
    assert respuesta["productos"], "hay una placa AM4 DDR4 Mini-ITX en el catálogo de prueba"
    for p in respuesta["productos"]:
        # Cada candidato, puesto en el armado, pasa las reglas que se pueden evaluar.
        reporte, _ = cliente.llamar_json("verificar_compatibilidad", motherboard=p["codigo"], **elegido)
        estados = {r["regla"]: r["estado"] for r in reporte["resultados"]}
        assert estados["socket_cpu_placa"] == estados["generacion_cpu_placa"] == estados["tipo_ram"] \
            == estados["formato_placa_gabinete"] == "cumple"


def test_filtros_compatibles_fuente_y_gpu(catalogo):
    piezas = {s: catalogo.obtener(c) for s, c in ARMADO.items()}
    # Fuente: la cuenta da (65 + 115 + 75) × 1,3 = 332 W, pero la GPU003 pide 550 W: manda lo más exigente.
    assert filtros_compatibles("fuente", piezas)[0] == {"potencia_w__min": 550}
    # GPU: que la fuente de 650 W alcance para lo que pide el fabricante y que entre en el gabinete.
    # Nunca por consumo_w: el catálogo real no lo trae y el filtro dejaría afuera todas las placas.
    filtros, notas = filtros_compatibles("gpu", piezas)
    assert filtros == {"largo_mm__max": 360, "fuente_recomendada_w__max": 650} and notas == []


def test_filtros_compatibles_avisa_si_falta_el_dato():
    cpu_sin_consumo = Producto(codigo="CPU-X", nombre="cpu", categoria="cpu", categoria_origen="cpu", precio=1,
                               stock=1, atributos={"socket": "AM4"})
    filtros, notas = filtros_compatibles("fuente", {"cpu": cpu_sin_consumo})
    assert filtros == {} and "consumo_max_w" in notas[0]


def test_candidatos_de_ram_son_siempre_dimm(catalogo):
    filtros, _ = filtros_compatibles("ram", {"cpu": catalogo.obtener("CPU002")})
    assert filtros == {"formato_modulo": "DIMM"}


def test_candidatos_con_cantidades_y_segundo_disco(catalogo):
    placa = catalogo.obtener("MOT001")   # 2 ranuras de RAM, 1 ranura M.2
    # Dos unidades de RAM en 2 ranuras: cada producto tiene que ser de 1 módulo.
    filtros, _ = filtros_compatibles("ram", {"motherboard": placa}, cantidades={"ram": 2})
    assert filtros["modulos__max"] == 1
    # La ranura M.2 ya la usa el disco principal: el segundo disco tiene que ser SATA.
    nvme = next(p for p in catalogo.buscar(categoria="almacenamiento", solo_con_stock=False, limite=50)
                if p.atributos["conexion"] == "M.2")
    filtros, _ = filtros_compatibles("almacenamiento", {"motherboard": placa, "almacenamiento": nvme},
                                     lugar="almacenamiento_extra")
    assert filtros == {"conexion": "SATA"}


def test_verificar_compatibilidad_con_cantidades(cliente):
    reporte, _ = cliente.llamar_json("verificar_compatibilidad", **ARMADO, cantidades={"ram": 2})
    precio_ram = next(p for p in reporte["resultados"] if p["regla"] == "ranuras_ram")
    assert precio_ram["estado"] == "cumple" and reporte["cantidades"]["ram"] == 2
    uno, _ = cliente.llamar_json("verificar_compatibilidad", **ARMADO)
    _, ram = cliente.llamar_json("obtener_producto", codigo=ARMADO["ram"])
    assert reporte["total"] == uno["total"] + ram["producto"]["precio"]


def test_busqueda_de_texto_primero_todas_las_palabras(catalogo):
    """«fuente corsair»: primero las fuentes Corsair; después, lo que coincide con una sola palabra."""
    resultados = catalogo.buscar(texto="fuente corsair", solo_con_stock=False, limite=10)
    con_ambas = [p for p in resultados if p.categoria == "fuente" and (p.marca or "").lower() == "corsair"]
    assert len(con_ambas) == 3
    assert resultados[:3] == con_ambas
    assert len(resultados) > 3   # se completa con coincidencias parciales


def test_el_agente_usa_el_catalogo_por_mcp_y_el_artifact_llega_a_los_eventos(cliente):
    modelo = modelo_con(llamada("buscar_productos", {"categoria": "ups", "atributos": {"va__min": 1500}}),
                        texto("Te recomiendo la UPS006."))
    mensajes = crear_agente(modelo, cliente).invoke({"messages": [("user", "una UPS grande")]},
                                                    context=Context(turn=1))["messages"]
    resultado = next(e for e in eventos(mensajes) if e["tipo"] == "resultado")
    assert json.loads(resultado["texto"])["cantidad"] >= 1
    assert all(p["atributos"]["va"] >= 1500 for p in resultado["datos"]["productos"])


def test_la_busqueda_para_el_armado_no_ofrece_plataformas_viejas(cliente):
    """Problema 33: con para_lugar (búsqueda del armado), las CPU, placas y memorias fuera del armado no salen."""
    from mcp_tienda.ingesta.extraccion import SOCKETS
    for categoria in ("cpu", "motherboard"):
        respuesta, _ = cliente.llamar_json("buscar_productos", categoria=categoria, para_lugar=categoria,
                                           solo_con_stock=False, limite=20)
        assert all(p["atributos"].get("socket") in SOCKETS for p in respuesta["productos"]), categoria
    respuesta, _ = cliente.llamar_json("buscar_productos", categoria="ram", para_lugar="ram",
                                       solo_con_stock=False, limite=20)
    assert all(p["atributos"].get("formato_modulo") == "DIMM" for p in respuesta["productos"])


def test_plataformas_viejas_quedan_fuera_del_armado_pero_salen_en_busqueda_comun(tmp_path, monkeypatch):
    """Problema 33: CPU 775, placa 775, RAM DDR3 y SODIMM no salen al buscar para armado, pero sí en búsqueda común."""
    from mcp_tienda.catalogo import Catalogo
    from mcp_tienda.modelos import Producto
    from mcp_tienda.servidor import buscar_productos as buscar_mcp

    def _p(codigo: str, nombre: str, categoria: str, precio: float, **atributos) -> Producto:
        return Producto(codigo=codigo, nombre=nombre, categoria=categoria, categoria_origen=categoria,
                        precio=precio, stock=5, atributos=atributos)

    ruta = tmp_path / "legado.sqlite"
    Catalogo(ruta).recrear([
        _p("CEL775", "CPU Intel Celeron 430 775", "cpu", 30000, socket="LGA775", generacion="0"),
        _p("RY5500", "CPU AMD Ryzen 5 5500", "cpu", 150000, socket="AM4", generacion="3"),
        _p("MB775", "Motherboard Intel DG31PR 775 DDR2", "motherboard", 40000, socket="LGA775", tipo_ram="DDR2"),
        _p("MBAM4", "Motherboard B550M AM4 DDR4", "motherboard", 120000,
           socket="AM4", generaciones=["3"], tipo_ram="DDR4", formato="Micro-ATX", ranuras_ram=2),
        _p("RAMDDR3", "Memoria 8GB DDR3 1600 DIMM", "ram", 20000,
           tipo="DDR3", capacidad_gb=8, modulos=1, formato_modulo="DIMM"),
        _p("RAMSOD", "Memoria 8GB DDR4 3200 SODIMM", "ram", 25000,
           tipo="DDR4", capacidad_gb=8, modulos=1, formato_modulo="SODIMM"),
        _p("RAMDDR4", "Memoria 8GB DDR4 3200 DIMM", "ram", 30000,
           tipo="DDR4", capacidad_gb=8, modulos=1, formato_modulo="DIMM"),
    ])
    monkeypatch.setenv("AMN_CATALOGO_DB", str(ruta))

    def _codigos(**kwargs):
        res = buscar_mcp(**kwargs)
        return [p["codigo"] for p in json.loads(res.content[0].text)["productos"]]

    # En armado (para_lugar / compatible_con), lo viejo y SODIMM quedan afuera.
    assert _codigos(categoria="cpu", para_lugar="cpu") == ["RY5500"]
    assert _codigos(categoria="motherboard", para_lugar="motherboard") == ["MBAM4"]
    assert _codigos(categoria="motherboard", compatible_con={"cpu": "RY5500"}) == ["MBAM4"]
    assert _codigos(categoria="ram", para_lugar="ram") == ["RAMDDR4"]

    # En búsqueda común siguen disponibles para quien busca un repuesto puntual.
    assert set(_codigos(categoria="cpu")) == {"CEL775", "RY5500"}
    assert set(_codigos(categoria="motherboard")) == {"MB775", "MBAM4"}
    assert set(_codigos(categoria="ram")) == {"RAMDDR3", "RAMSOD", "RAMDDR4"}


def test_el_filtro_de_gama_encuentra_piezas_caras_aunque_haya_muchas_baratas(tmp_path, monkeypatch):
    """La gama no está en la base: se filtra después de buscar. Antes se traían solo los 50 más
    baratos, así que con muchos procesadores de gama baja el de gama alta nunca aparecía y la
    búsqueda volvía vacía (pasa con el catálogo real: el único CPU premium quedaba afuera)."""
    import json

    from mcp_tienda import servidor
    from mcp_tienda.catalogo import Catalogo
    from tests.conftest import TABLA_GAMAS

    baratos = [Producto(codigo=f"B{i:03}", nombre="AMD Ryzen 3 4100", categoria="cpu", categoria_origen="cpu",
                        precio=100_000 + i, stock=5) for i in range(60)]
    caro = Producto(codigo="ALTA1", nombre="AMD Ryzen 7 7800X3D", categoria="cpu", categoria_origen="cpu",
                    precio=900_000, stock=1)
    ruta = tmp_path / "catalogo.sqlite"
    Catalogo(ruta).recrear([*baratos, caro])
    monkeypatch.setenv("AMN_CATALOGO_DB", str(ruta))
    monkeypatch.setenv("AMN_TABLA_GAMAS", str(TABLA_GAMAS))

    resultado = json.loads(servidor.buscar_productos(categoria="cpu", gama="alta").content[0].text)
    assert [p["codigo"] for p in resultado["productos"]] == ["ALTA1"]
