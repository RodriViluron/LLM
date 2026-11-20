"""Paso 4: el armado de PC vive en el estado del agente.

Las pruebas usan el servidor MCP real y un modelo falso. La de dos turnos es la que pide
CLAUDE.md: «cambiá la placa de video por una más potente» funciona en el segundo turno.
"""

import json

import pytest
from langchain_core.messages import AIMessage

import agente as modulo_agente
import armado
from agente import crear_agente, crear_checkpointer, new_thread, saved_state, stream_turn
from mcp_tienda.armado.gamas import buscar_fila, clasificar_gama
from tests.conftest import TABLA_GAMAS
from tests.falsos import buscar, llamada, modelo_con, texto
from tools import Context

ARMADO = {"cpu": "CPU002", "motherboard": "MOT003", "ram": "RAM003", "gpu": "GPU003",
          "almacenamiento": "ALM003", "fuente": "FUE006", "gabinete": "GAB004"}


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo_agente, "CONV_FILE", tmp_path / "conversaciones.txt")


@pytest.fixture
def armada(cliente) -> dict:
    """Configuración completa y compatible, armada pieza por pieza."""
    config = armado.nueva(presupuesto=1_200_000, perfil_uso="juegos 1080p")
    for lugar, codigo in ARMADO.items():
        config = armado.poner_componente(config, lugar, codigo, cliente)
    return config


def _agregar(lugar: str, codigo: str, n: int):
    return llamada("agregar_o_reemplazar_componente", {"lugar": lugar, "codigo": codigo}, f"a{n}")


# --- El caso de CLAUDE.md: dos turnos ---------------------------------------------

def test_segundo_turno_cambia_solo_la_placa_de_video(cliente, catalogo, tmp_path):
    ruta = tmp_path / "memoria.db"
    config = new_thread()

    # Turno 1: el modelo inicia el armado y agrega las 7 piezas, de a una.
    pasos = [llamada("iniciar_configuracion", {"presupuesto": 1_200_000, "perfil_uso": "juegos 1080p"}, "i")]
    # Por cada pieza, busca y después agrega (solo se aceptan códigos que salieron de una búsqueda).
    for n, (lugar, codigo) in enumerate(ARMADO.items()):
        pasos += [buscar(lugar), _agregar(lugar, codigo, n)]
    agente_1 = crear_agente(modelo_con(*pasos, texto("Listo, te armé la PC.")), cliente, crear_checkpointer(ruta))
    eventos_1 = list(stream_turn("Armame una PC para jugar con $1.200.000", config, 1, agente_1))

    antes = saved_state(config, agente_1)["configuracion"]
    assert {s: p["codigo"] for s, p in antes["componentes"].items()} == ARMADO
    assert antes["reporte"]["estado_general"] == "compatible"
    assert antes["total"] == sum(catalogo.obtener(c).precio for c in ARMADO.values())
    assert antes["presupuesto"] == 1_200_000 and antes["perfil_uso"] == "juegos 1080p"

    # Lo que leyó el modelo es un resumen; la configuración completa fue a la interfaz por artifact.
    ultimo = [e for e in eventos_1 if e["tipo"] == "resultado"][-1]
    assert "descripcion" not in ultimo["texto"]
    assert ultimo["datos"]["configuracion"]["componentes"]["gabinete"]["descripcion"]

    # Turno 2, con el programa «reabierto»: el modelo lee el armado, busca y cambia solo la GPU.
    agente_2 = crear_agente(
        modelo_con(
            llamada("obtener_configuracion", {}, "o"),
            llamada("buscar_productos", {"categoria": "gpu", "compatible_con": ARMADO, "precio_min": 500_000}, "b"),
            _agregar("gpu", "GPU005", 99),
            texto("Te cambié la placa de video por la RTX 4060 Ti."),
        ),
        cliente, crear_checkpointer(ruta),
    )
    eventos_2 = list(stream_turn("Cambiá la placa de video por una más potente", config, 2, agente_2))

    # obtener_configuracion encontró en el estado lo que se armó en el turno 1.
    leido = json.loads(next(e for e in eventos_2 if e["tipo"] == "resultado")["texto"])["configuracion"]
    assert leido["componentes"]["gpu"]["codigo"] == "GPU003" and leido["faltan"] == []

    despues = saved_state(config, agente_2)["configuracion"]
    assert despues["componentes"]["gpu"]["codigo"] == "GPU005"
    for lugar in set(ARMADO) - {"gpu"}:
        assert despues["componentes"][lugar] == antes["componentes"][lugar], lugar
    assert despues["ultimos_cambios"] == ["gpu"]
    # La tienda re-verificó y recalculó: no lo hizo el modelo.
    assert despues["reporte"]["estado_general"] == "compatible"
    diferencia = catalogo.obtener("GPU005").precio - catalogo.obtener("GPU003").precio
    assert despues["total"] == antes["total"] + diferencia


def test_varias_piezas_en_un_mismo_mensaje_no_se_pierden(cliente):
    """El modelo puede pedir varias tools a la vez: el reducer del estado las fusiona."""
    de_una = AIMessage(content="", tool_calls=[
        {"name": "agregar_o_reemplazar_componente", "args": {"lugar": lugar, "codigo": codigo}, "id": lugar}
        for lugar, codigo in list(ARMADO.items())[:3]
    ])
    busquedas = [buscar(lugar) for lugar in list(ARMADO)[:3]]
    agente = crear_agente(modelo_con(*busquedas, de_una, llamada("obtener_configuracion", {}, "o"), texto("ok")),
                          cliente)
    config = agente.invoke({"messages": [("user", "armá")]}, context=Context(turn=1))["configuracion"]
    assert set(config["componentes"]) == {"cpu", "motherboard", "ram"}
    assert config["reporte"] is not None   # obtener_configuracion la dejó verificada


def test_fusionar_marca_sin_verificar_cuando_llegan_cambios_a_la_vez(armada):
    base = {**armada, "version": 5}
    primera = {**base, "version": 6, "ultimos_cambios": ["gpu"],
               "componentes": {**base["componentes"], "gpu": {"codigo": "G1", "precio": 10.0}}}
    segunda = {**base, "version": 6, "ultimos_cambios": ["cooler"],
               "componentes": {**base["componentes"], "cooler": {"codigo": "C1", "precio": 5.0}}}
    estado = armado.fusionar(base, primera)
    assert estado is primera                      # versión siguiente: reemplaza
    estado = armado.fusionar(estado, segunda)     # misma versión: se aplican solo sus cambios
    assert estado["componentes"]["gpu"]["codigo"] == "G1" and estado["componentes"]["cooler"]["codigo"] == "C1"
    assert estado["reporte"] is None and estado["version"] == 7
    assert estado["total"] == round(sum(p["precio"] for p in estado["componentes"].values()), 2)


def test_las_tools_devuelven_error_y_no_tocan_el_estado(cliente):
    agente = crear_agente(modelo_con(buscar("gpu"), _agregar("cpu", "GPU003", 1), _agregar("cpu", "NOEXISTE", 2),
                                     llamada("ajustar_presupuesto", {}, "j"), texto("no pude")), cliente)
    resultado = agente.invoke({"messages": [("user", "x")]}, context=Context(turn=1))
    errores = [json.loads(m.content)["error"] for m in resultado["messages"]
               if m.type == "tool" and m.name != "buscar_productos"]
    assert "no puede ir en el lugar 'cpu'" in errores[0]
    assert "no salió de ninguna búsqueda" in errores[1]   # un código inventado se frena antes de consultar
    assert "No hay ningún armado" in errores[2]
    assert not resultado["configuracion"]   # sigue vacía


def test_iniciar_configuracion_borra_el_armado_anterior(cliente):
    pasos = [_agregar("cpu", "CPU002", 1), llamada("iniciar_configuracion", {"presupuesto": 500_000}, "i"), texto("ok")]
    agente = crear_agente(modelo_con(*pasos), cliente)
    config = agente.invoke({"messages": [("user", "x")]}, context=Context(turn=1))["configuracion"]
    assert config["componentes"] == {} and config["presupuesto"] == 500_000 and config["total"] == 0


# --- ajustar_presupuesto -------------------------------------------------------------

def _gamas(config: dict) -> dict:
    return {s: config["componentes"][s]["gama"] for s in ("cpu", "gpu")}


@pytest.mark.parametrize("presupuesto", [990_000, 900_000])
def test_ajustar_presupuesto_entra_sin_bajar_de_gama(armada, cliente, presupuesto):
    ajustada, informe = armado.ajustar_presupuesto({**armada, "presupuesto": presupuesto}, cliente)
    assert informe["dentro_del_presupuesto"] and ajustada["total"] <= presupuesto
    assert informe["cambios"] and informe["vueltas"] <= informe["tope"]
    assert _gamas(ajustada) == _gamas(armada) == {"cpu": "media", "gpu": "media"}
    assert ajustada["reporte"]["estado_general"] == "compatible"
    # RAM y disco no pierden capacidad.
    for lugar in ("ram", "almacenamiento"):
        nueva, vieja = ajustada["componentes"][lugar]["atributos"], armada["componentes"][lugar]["atributos"]
        assert nueva["capacidad_gb"] >= vieja["capacidad_gb"]
    # El informe explica qué se cedió y cierra con el total.
    assert sum(c["ahorro"] for c in informe["cambios"]) == armada["total"] - ajustada["total"]


def test_ajustar_presupuesto_cede_lo_minimo_si_un_cambio_alcanza(armada, cliente):
    """Faltan $26.000: alcanza con un cambio y se elige el que menos resigna, no el que más ahorra."""
    _, informe = armado.ajustar_presupuesto({**armada, "presupuesto": 990_000}, cliente)
    assert len(informe["cambios"]) == 1
    assert 26_000 <= informe["cambios"][0]["ahorro"] < 105_000


def test_ajustar_presupuesto_imposible_termina_y_lo_dice(armada, cliente):
    ajustada, informe = armado.ajustar_presupuesto({**armada, "presupuesto": 100_000}, cliente)
    assert not informe["dentro_del_presupuesto"]
    assert informe["vueltas"] <= armado.TOPE_ITERACIONES
    assert informe["falta_ahorrar"] == ajustada["total"] - 100_000 and informe["motivo"]
    assert _gamas(ajustada) == _gamas(armada)   # ni siendo imposible baja de gama


def test_ajustar_presupuesto_respeta_el_tope_de_vueltas(armada, cliente):
    _, informe = armado.ajustar_presupuesto({**armada, "presupuesto": 900_000}, cliente, tope=1)
    assert informe["vueltas"] == 1 and "tope" in informe["motivo"] and not informe["dentro_del_presupuesto"]


def test_ajustar_presupuesto_no_reemplaza_piezas_sin_datos_de_gama(cliente):
    """El Ryzen 9 7900X no está en la tabla de gamas: no se toca, y se avisa."""
    config = armado.poner_componente(armado.nueva(presupuesto=100_000), "cpu", "CPU010", cliente)
    assert config["componentes"]["cpu"]["gama"] is None
    ajustada, informe = armado.ajustar_presupuesto(config, cliente)
    assert ajustada["componentes"]["cpu"]["codigo"] == "CPU010"
    assert informe["sin_datos_de_gama"] == ["cpu"] and "tabla de gamas" in informe["nota"]


def test_ajustar_presupuesto_sin_presupuesto_es_error(armada, cliente):
    with pytest.raises(armado.ErrorArmado):
        armado.ajustar_presupuesto({**armada, "presupuesto": None}, cliente)


def test_tool_ajustar_presupuesto_guarda_y_explica(armada, cliente):
    agente = crear_agente(modelo_con(llamada("ajustar_presupuesto", {}, "j"), texto("ajustado")), cliente)
    entrada = {"messages": [("user", "ajustá")], "configuracion": {**armada, "presupuesto": 990_000}}
    resultado = agente.invoke(entrada, context=Context(turn=1))
    respuesta = json.loads(next(m.content for m in resultado["messages"] if m.type == "tool"))
    assert respuesta["ajuste"]["dentro_del_presupuesto"] and respuesta["ajuste"]["cambios"]
    assert respuesta["configuracion"]["dentro_del_presupuesto"]
    assert resultado["configuracion"]["total"] == respuesta["configuracion"]["total"] <= 990_000


# --- Resumen, alternativas y gamas ------------------------------------------------------

def test_resumen_para_el_modelo(armada):
    resumen = armado.resumen(armada)
    assert resumen["faltan"] == [] and resumen["compatibilidad"] == "compatible"
    assert resumen["dentro_del_presupuesto"] is True and "excedente" not in resumen
    assert resumen["componentes"]["cpu"] == {"codigo": "CPU002", "nombre": armada["componentes"]["cpu"]["nombre"],
                                             "precio": 145000.0, "stock": 1, "gama": "media"}
    # Piezas sin stock en el catálogo de prueba: se le avisa al modelo.
    assert resumen["sin_stock"] == [s for s, p in armada["componentes"].items() if p["stock"] == 0] != []
    incompleta = armado.resumen({**armado.nueva(1000), "componentes": {}, "total": 0})
    assert incompleta["faltan"] == ["cpu", "motherboard", "ram", "almacenamiento", "fuente", "gabinete"]
    assert incompleta["compatibilidad"] == "sin_verificar"


def test_alternativas_para_el_boton_cambiar(armada, cliente):
    opciones = armado.alternativas(armada, "gpu", cliente)
    assert opciones and all(p["categoria"] == "gpu" and p["codigo"] != "GPU003" for p in opciones)
    for p in opciones:   # cada alternativa, puesta en el armado, no rompe ninguna regla
        probada = armado.poner_componente(armada, "gpu", p["codigo"], cliente)
        assert probada["reporte"]["estado_general"] != "incompatible", p["codigo"]


def test_gama_por_tabla():
    assert clasificar_gama("MSI GeForce RTX 4060 Ti Ventus 2X 8G", "gpu", TABLA_GAMAS) == "media"
    # forma normalizada: el sufijo va pegado al número («Ti» es parte del modelo)
    assert buscar_fila("MSI GeForce RTX 4060 Ti Ventus 2X", "gpu", TABLA_GAMAS)["modelo"] == "rtx 4060ti"
    assert buscar_fila("ASUS Dual GeForce RTX 4060 OC", "gpu", TABLA_GAMAS)["modelo"] == "rtx 4060"
    # 5600 y 5600G son modelos distintos: cada uno coincide solo con su fila.
    assert buscar_fila("PROCESADOR AMD Ryzen 5 5600G", "cpu", TABLA_GAMAS)["puntaje"] == 55
    assert buscar_fila("Micro AMD Ryzen 5 5600 am4", "cpu", TABLA_GAMAS)["puntaje"] == 60
    assert clasificar_gama("Intel Core i3-12100F", "cpu", TABLA_GAMAS) == "baja"   # guiones y mayúsculas


def test_gama_sin_datos_nunca_se_adivina(tmp_path):
    assert clasificar_gama("AMD Ryzen 9 7900X", "cpu", TABLA_GAMAS) is None          # no está en la tabla
    assert clasificar_gama("Corsair RM750e", "fuente", TABLA_GAMAS) is None          # la gama no aplica
    assert clasificar_gama("AMD Ryzen 5 5600", "cpu", tmp_path / "no_existe.md") is None   # tabla sin escribir


def test_el_servidor_informa_y_filtra_por_gama(cliente):
    respuesta, _ = cliente.llamar_json("buscar_productos", categoria="gpu", gama="alta", solo_con_stock=False,
                                       limite=20)
    assert respuesta["productos"] and all(p["gama"] == "alta" for p in respuesta["productos"])
    assert "no están en la tabla de gamas" in " ".join(respuesta["notas"])
    assert "error" in cliente.llamar_json("buscar_productos", categoria="fuente", gama="alta")[0]
    assert cliente.llamar_json("obtener_producto", codigo="CPU010")[0]["gama"] == "sin datos"


def test_la_skill_de_armado_se_carga():
    from tools import listar_skills, load_skill

    assert listar_skills().startswith("armado_pc: Procedimiento para elegir y comprar las piezas de una PC")
    contenido = load_skill.invoke({"nombre": "armado_pc"})
    for tool in ("iniciar_configuracion", "agregar_o_reemplazar_componente", "ajustar_presupuesto",
                 "obtener_configuracion", "compatible_con", "write_todos"):
        assert tool in contenido


# --- Cantidades y segundo disco ---------------------------------------------------------

def test_ram_con_cantidad_y_segundo_disco(armada, cliente, catalogo):
    precio_ram = catalogo.obtener("RAM003").precio
    doble = armado.poner_componente(armada, "ram", "RAM003", cliente, cantidad=2)
    assert doble["cantidades"] == {"ram": 2}
    assert doble["total"] == armada["total"] + precio_ram
    assert armado.resumen(doble)["componentes"]["ram"]["cantidad"] == 2
    reglas = {r["regla"]: r["estado"] for r in doble["reporte"]["resultados"]}
    assert reglas["ranuras_ram"] == "cumple"

    hdd = next(p for p in catalogo.buscar(categoria="almacenamiento", limite=50) if p.atributos["tipo"] == "HDD")
    con_hdd = armado.poner_componente(doble, "almacenamiento_extra", hdd.codigo, cliente)
    assert con_hdd["total"] == doble["total"] + hdd.precio
    assert con_hdd["componentes"]["almacenamiento_extra"]["codigo"] == hdd.codigo

    # Reemplazar la RAM con cantidad 1 vuelve a una unidad; quitar el disco lo saca del total.
    simple = armado.poner_componente(con_hdd, "ram", "RAM003", cliente)
    assert simple["cantidades"] == {}
    assert armado.quitar_componente(simple, "almacenamiento_extra", cliente)["total"] == armada["total"]


def test_cantidad_invalida_se_rechaza(armada, cliente):
    with pytest.raises(armado.ErrorArmado):
        armado.poner_componente(armada, "cpu", "CPU002", cliente, cantidad=2)
    with pytest.raises(armado.ErrorArmado):
        armado.poner_componente(armada, "ram", "RAM003", cliente, cantidad=9)


def test_fusionar_conserva_cantidades():
    actual = {**armado.nueva(), "version": 3, "componentes": {"ram": {"precio": 10.0}}, "cantidades": {"ram": 2}}
    propuesta = {**armado.nueva(), "version": 3, "ultimos_cambios": ["almacenamiento"],
                 "componentes": {"almacenamiento": {"precio": 5.0}}, "cantidades": {"almacenamiento": 3}}
    fusionada = armado.fusionar(actual, propuesta)
    assert fusionada["cantidades"] == {"ram": 2, "almacenamiento": 3} and fusionada["total"] == 35.0
