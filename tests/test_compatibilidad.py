import pytest

from mcp_tienda.armado.reglas import lugares_obligatorios, verificar_compatibilidad
from mcp_tienda.modelos import Configuracion, Producto


def producto(categoria: str, codigo: str = None, precio: float = 1000, **atributos) -> Producto:
    return Producto(codigo=codigo or categoria.upper(), nombre=codigo or categoria, categoria=categoria,
                    categoria_origen=categoria, precio=precio, stock=1, atributos=atributos)


def cpu(**cambios) -> Producto:
    base = dict(socket="AM4", nucleos=6, tdp_w=65, generacion="3", incluye_cooler="si", video_integrado="no")
    return producto("cpu", **(base | cambios))


def armado_valido(**reemplazos) -> dict:
    base = {
        "cpu": cpu(),
        "motherboard": producto("motherboard", socket="AM4", tipo_ram="DDR4", formato="Micro-ATX",
                                generaciones=["2", "3"], ranuras_ram=2, ranuras_m2=1, puertos_sata=4),
        "ram": producto("ram", tipo="DDR4", capacidad_gb=16, frecuencia_mhz=3200, formato_modulo="DIMM", modulos=1),
        "gpu": producto("gpu", vram_gb=8, consumo_w=115, largo_mm=227),
        "almacenamiento": producto("almacenamiento", tipo="NVMe", capacidad_gb=1000, conexion="M.2"),
        "fuente": producto("fuente", potencia_w=550, certificacion="80 Plus Bronze"),
        "gabinete": producto("gabinete", formatos_admitidos=["Micro-ATX", "Mini-ITX"], largo_max_gpu_mm=350),
    }
    base.update(reemplazos)
    return {k: v for k, v in base.items() if v is not None}   # None = sacar la pieza


def resultados(cantidades: dict | None = None, **reemplazos) -> dict:
    config = Configuracion(componentes=armado_valido(**reemplazos), cantidades=cantidades or {})
    reporte = verificar_compatibilidad(config)
    return {r.regla: r for r in reporte.resultados}


def estados(config: Configuracion) -> dict[str, str]:
    return {r.regla: r.estado for r in verificar_compatibilidad(config).resultados}


def test_armado_valido_cumple_todo():
    config = Configuracion(componentes=armado_valido())
    reporte = verificar_compatibilidad(config)
    assert reporte.estado_general == "compatible"
    # conectores_gpu no tiene datos en el armado sintético: es un aviso, no bloquea.
    assert {e for r, e in estados(config).items() if r != "conectores_gpu"} == {"cumple"}
    assert reporte.avisos and reporte.avisos[0].startswith("conectores_gpu")
    assert config.total == 7000


@pytest.mark.parametrize("reemplazo, regla", [
    ({"cpu": cpu(socket="AM5")}, "socket_cpu_placa"),
    ({"cpu": cpu(generacion="4")}, "generacion_cpu_placa"),
    ({"ram": producto("ram", tipo="DDR5", formato_modulo="DIMM")}, "tipo_ram"),
    ({"ram": producto("ram", tipo="DDR4", formato_modulo="SODIMM")}, "modulo_ram"),
    ({"ram": producto("ram", tipo="DDR4", formato_modulo="ECC")}, "modulo_ram"),
    ({"ram": producto("ram", tipo="DDR4", formato_modulo="DIMM", modulos=4)}, "ranuras_ram"),
    ({"almacenamiento_extra": producto("almacenamiento", "ALM2", tipo="NVMe", conexion="M.2")},
     "puertos_almacenamiento"),
    ({"fuente": producto("fuente", potencia_w=300)}, "potencia_fuente"),
    ({"gabinete": producto("gabinete", formatos_admitidos=["Mini-ITX"], largo_max_gpu_mm=400)},
     "formato_placa_gabinete"),
    ({"gpu": producto("gpu", consumo_w=115, largo_mm=360)}, "largo_gpu_gabinete"),
    ({"cooler": producto("cooler", sockets=["LGA1700"], potencia_enfriamiento_w=200)}, "socket_cooler"),
    ({"cooler": producto("cooler", sockets=["AM4"], potencia_enfriamiento_w=50)}, "potencia_cooler"),
    ({"gpu": producto("gpu", consumo_w=115, largo_mm=227, conectores_energia="2x8pin"),
      "fuente": producto("fuente", potencia_w=550, conectores_pcie=1)}, "conectores_gpu"),
])
def test_cada_regla_detecta_su_incompatibilidad(reemplazo, regla):
    config = Configuracion(componentes=armado_valido(**reemplazo))
    assert estados(config)[regla] == "no_cumple"
    assert verificar_compatibilidad(config).estado_general == "incompatible"


def test_potencia_con_margen():
    # Consumo 65 + 115 + 75 = 255 W; con 30 % de margen hacen falta 331,5 W.
    justa = Configuracion(componentes=armado_valido(fuente=producto("fuente", potencia_w=332)))
    corta = Configuracion(componentes=armado_valido(fuente=producto("fuente", potencia_w=331)))
    assert estados(justa)["potencia_fuente"] == "cumple"
    assert estados(corta)["potencia_fuente"] == "no_cumple"


def test_potencia_usa_la_fuente_recomendada_de_la_gpu_si_es_mas_exigente():
    # Catálogo real: la GPU no informa consumo pero sí la fuente que pide el fabricante.
    gpu = producto("gpu", fuente_recomendada_w=550)
    r = resultados(gpu=gpu, fuente=producto("fuente", potencia_w=500))["potencia_fuente"]
    assert r.estado == "no_cumple" and "550" in r.detalle and "recomienda" in r.detalle
    assert resultados(gpu=gpu, fuente=producto("fuente", potencia_w=550))["potencia_fuente"].estado == "cumple"


def test_potencia_con_cpu_muy_exigente_supera_la_recomendada():
    # (253 + 75) × 1,3 = 426,4 W de la CPU sola: si la GPU recomienda 400 W, manda la cuenta.
    r = resultados(cpu=cpu(consumo_max_w=253, tdp_w=125), gpu=producto("gpu", fuente_recomendada_w=400),
                   fuente=producto("fuente", potencia_w=420))["potencia_fuente"]
    assert r.estado == "no_cumple" and "426" in r.detalle


def test_potencia_usa_consumo_maximo_antes_que_tdp():
    # 117 + 115 + 75 = 307 → 399,1 W; con el TDP (65) alcanzaría con 332 W.
    r = resultados(cpu=cpu(consumo_max_w=117), fuente=producto("fuente", potencia_w=350))["potencia_fuente"]
    assert r.estado == "no_cumple"


def test_potencia_con_la_fuente_del_gabinete():
    gabinete = producto("gabinete", formatos_admitidos=["Micro-ATX"], largo_max_gpu_mm=350,
                        incluye_fuente="si", potencia_fuente_w=500)
    todos = resultados(gabinete=gabinete, fuente=None)
    assert todos["potencia_fuente"].estado == "cumple" and "gabinete" in todos["potencia_fuente"].detalle
    assert "fuente" not in lugares_obligatorios({"gabinete": gabinete.atributos})
    sin_potencia = producto("gabinete", formatos_admitidos=["Micro-ATX"], incluye_fuente="si")
    assert resultados(gabinete=sin_potencia, fuente=None)["potencia_fuente"].estado == "sin_datos"


def test_sin_gpu_no_evalua_largo_y_calcula_consumo_sin_gpu():
    todos = resultados(cpu=cpu(video_integrado="si"), gpu=None)
    assert "largo_gpu_gabinete" not in todos and "conectores_gpu" not in todos
    assert "GPU 0" in todos["potencia_fuente"].detalle
    assert todos["video"].estado == "cumple"


def test_gpu_sin_consumo_ni_fuente_recomendada_da_sin_datos():
    r = resultados(gpu=producto("gpu", vram_gb=2))["potencia_fuente"]
    assert r.estado == "sin_datos" and r.critica


@pytest.mark.parametrize("reemplazo, regla", [
    ({"cpu": cpu(socket=None)}, "socket_cpu_placa"),
    ({"cpu": cpu(generacion=None)}, "generacion_cpu_placa"),
    ({"motherboard": producto("motherboard", socket="AM4", tipo_ram=None, formato="Micro-ATX",
                              generaciones=["3"])}, "tipo_ram"),
    ({"ram": producto("ram", tipo="DDR4")}, "modulo_ram"),
    ({"cpu": cpu(video_integrado=None), "gpu": None}, "video"),
    ({"cpu": cpu(incluye_cooler=None)}, "cooler"),
    ({"cooler": producto("cooler", sockets=["AM4"])}, "potencia_cooler"),
])
def test_falta_un_atributo_critico_da_sin_datos_y_bloquea(reemplazo, regla):
    config = Configuracion(componentes=armado_valido(**reemplazo))
    resultado = next(r for r in verificar_compatibilidad(config).resultados if r.regla == regla)
    assert resultado.estado == "sin_datos" and resultado.critica
    assert "no informa" in resultado.detalle
    assert verificar_compatibilidad(config).estado_general == "sin_confirmar"


def test_falta_el_largo_es_aviso_no_bloquea():
    gabinete = producto("gabinete", formatos_admitidos=["Micro-ATX"], largo_max_gpu_mm=None)
    config = Configuracion(componentes=armado_valido(gabinete=gabinete))
    reporte = verificar_compatibilidad(config)
    largo = next(r for r in reporte.resultados if r.regla == "largo_gpu_gabinete")
    assert largo.estado == "sin_datos" and not largo.critica
    assert reporte.estado_general == "compatible"
    assert any(a.startswith("largo_gpu_gabinete") for a in reporte.avisos)


def test_falta_pieza_obligatoria_da_sin_datos():
    resultado = resultados(fuente=None)["potencia_fuente"]
    assert resultado.estado == "sin_datos" and "Falta elegir: fuente" in resultado.detalle


def test_cpu_sin_video_pide_placa_de_video():
    todos = resultados(gpu=None)
    assert todos["video"].estado == "sin_datos" and "Falta elegir: gpu" in todos["video"].detalle
    assert "gpu" in lugares_obligatorios({"cpu": cpu().atributos})


def test_cpu_sin_cooler_pide_cooler():
    todos = resultados(cpu=cpu(incluye_cooler="no"))
    assert todos["cooler"].estado == "sin_datos" and "Falta elegir: cooler" in todos["cooler"].detalle
    assert "cooler" in lugares_obligatorios({"cpu": cpu(incluye_cooler="no").atributos})
    con_cooler = resultados(cpu=cpu(incluye_cooler="no"),
                            cooler=producto("cooler", sockets=["AM4"], potencia_enfriamiento_w=150))
    assert con_cooler["cooler"].estado == "cumple" and con_cooler["potencia_cooler"].estado == "cumple"


def test_lugares_obligatorios_basicos():
    assert lugares_obligatorios({}) == ["cpu", "motherboard", "ram", "almacenamiento", "fuente", "gabinete"]


def test_cooler_socket():
    ok = Configuracion(componentes=armado_valido(
        cooler=producto("cooler", sockets=["AM4", "AM5"], potencia_enfriamiento_w=150)))
    mal = Configuracion(componentes=armado_valido(
        cooler=producto("cooler", sockets=["LGA1700"], potencia_enfriamiento_w=150)))
    assert estados(ok)["socket_cooler"] == "cumple"
    assert estados(mal)["socket_cooler"] == "no_cumple"


def test_conectores_16_pines_es_aviso():
    r = resultados(gpu=producto("gpu", consumo_w=115, largo_mm=227, conectores_energia="1x16pin"),
                   fuente=producto("fuente", potencia_w=550, conectores_pcie=4))["conectores_gpu"]
    assert r.estado == "sin_datos" and not r.critica


def test_producto_en_lugar_equivocado_se_rechaza():
    with pytest.raises(ValueError):
        Configuracion(componentes={"cpu": producto("gpu")})


def test_armado_real_del_catalogo(catalogo):
    codigos = {"cpu": "CPU002", "motherboard": "MOT003", "ram": "RAM003", "gpu": "GPU003",
               "almacenamiento": "ALM003", "fuente": "FUE006", "gabinete": "GAB004"}
    config = Configuracion(componentes={s: catalogo.obtener(c) for s, c in codigos.items()})
    assert verificar_compatibilidad(config).estado_general == "compatible"


# --- Cantidades y segundo disco -------------------------------------------------------

def test_ranuras_cuenta_la_cantidad():
    assert resultados(cantidades={"ram": 2})["ranuras_ram"].estado == "cumple"     # 2 módulos, 2 ranuras
    assert resultados(cantidades={"ram": 3})["ranuras_ram"].estado == "no_cumple"
    kit = producto("ram", tipo="DDR4", formato_modulo="DIMM", modulos=2)
    assert resultados(ram=kit, cantidades={"ram": 2})["ranuras_ram"].estado == "no_cumple"   # 2 kits de 2


def test_puertos_cuenta_m2_y_sata_por_separado():
    sata = producto("almacenamiento", "HDD", tipo="HDD", conexion="SATA")
    r = resultados(almacenamiento_extra=sata, cantidades={"almacenamiento_extra": 4})["puertos_almacenamiento"]
    assert r.estado == "cumple" and "4 disco(s) SATA" in r.detalle
    placa = producto("motherboard", socket="AM4", tipo_ram="DDR4", formato="Micro-ATX", generaciones=["3"],
                     ranuras_ram=2, ranuras_m2=1, puertos_sata=2)
    r = resultados(motherboard=placa, almacenamiento_extra=sata,
                   cantidades={"almacenamiento_extra": 3})["puertos_almacenamiento"]
    assert r.estado == "no_cumple"


def test_disco_m2_sata_da_sin_datos():
    m2_sata = producto("almacenamiento", tipo="M.2 SATA", conexion="M.2")
    r = resultados(almacenamiento=m2_sata)["puertos_almacenamiento"]
    assert r.estado == "sin_datos" and r.critica


def test_total_multiplica_por_la_cantidad():
    config = Configuracion(componentes=armado_valido(), cantidades={"ram": 2})
    assert config.total == 8000


def test_cantidad_solo_en_ram_y_discos():
    with pytest.raises(ValueError):
        Configuracion(componentes=armado_valido(), cantidades={"cpu": 2})
    with pytest.raises(ValueError):
        Configuracion(componentes=armado_valido(), cantidades={"ram": 9})


def test_segundo_disco_es_de_almacenamiento():
    Configuracion(componentes=armado_valido(almacenamiento_extra=producto("almacenamiento", "ALM2")))
    with pytest.raises(ValueError):
        Configuracion(componentes=armado_valido(almacenamiento_extra=producto("ram", "RAM2")))
