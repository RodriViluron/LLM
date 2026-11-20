"""Reparto del presupuesto: los armados al azar tienen que ser compatibles y los porcentajes, cerrar."""

import random

from evaluacion.reparto_presupuesto import COMPONENTES, CRITERIOS, armar, documento, medir


def _pieza(codigo: str, precio: float, **atributos) -> dict:
    return {"codigo": codigo, "nombre": codigo, "precio": precio, "stock": 1, **atributos}


def _catalogo() -> dict:
    """Un catálogo mínimo con una trampa por categoría: algo que NO es compatible y no debe elegirse."""
    return {
        "cpu": [
            _pieza("CPU AMD RYZEN 5 7600", 400, socket="AM5", generacion="4", video_integrado="si",
                   incluye_cooler="si", tdp_w=65, consumo_max_w=65),
            _pieza("CPU INTEL CORE I5 12400F", 380, socket="LGA1700", generacion="12", video_integrado="no",
                   incluye_cooler="no", tdp_w=65, consumo_max_w=117),
        ],
        "motherboard": [
            _pieza("MB B650M AM5", 250, socket="AM5", generaciones=["4", "5"], tipo_ram="DDR5", formato="Micro-ATX",
                   ranuras_ram=2, ranuras_m2=1),
            _pieza("MB B760M 1700", 220, socket="LGA1700", generaciones=["12", "13", "14"], tipo_ram="DDR4",
                   formato="Micro-ATX", ranuras_ram=2, ranuras_m2=1),
            _pieza("MB B850 VIEJA", 100, socket="AM5", generaciones=["5"], tipo_ram="DDR5", formato="Micro-ATX",
                   ranuras_ram=2, ranuras_m2=1),   # trampa: no soporta la generación 4
        ],
        "ram": [
            _pieza("16GB DDR5", 600, tipo="DDR5", capacidad_gb=16, modulos=1, formato_modulo="DIMM"),
            _pieza("8GB DDR4", 200, tipo="DDR4", capacidad_gb=8, modulos=1, formato_modulo="DIMM"),
            _pieza("16GB DDR5 NOTEBOOK", 50, tipo="DDR5", capacidad_gb=16, modulos=1, formato_modulo="SODIMM"),
        ],
        "almacenamiento": [_pieza("NVME 1TB", 430, tipo="NVMe", capacidad_gb=1000),
                           _pieza("HDD 1TB", 60, tipo="HDD", capacidad_gb=1000)],
        "gpu": [_pieza("PL.VIDEO GF RTX5050", 900, fuente_recomendada_w=550),
                _pieza("PL.VIDEO GF RTX5050 SIN DATO", 100, fuente_recomendada_w=None)],
        "fuente": [_pieza("FTE 600W", 110, potencia_w=600, certificacion="80 Plus Bronze"),
                   _pieza("FTE 500W", 30, potencia_w=500, certificacion=None)],   # trampa: no llega a 550 W
        "gabinete": [_pieza("GAB MATX", 90, incluye_fuente="no", formatos_admitidos=["Micro-ATX", "Mini-ITX"]),
                     _pieza("GAB ITX", 40, incluye_fuente="no", formatos_admitidos=["Mini-ITX"]),
                     _pieza("GAB CON FUENTE", 20, incluye_fuente="si", formatos_admitidos=["Micro-ATX"])],
        "cooler": [_pieza("COOLER 130W", 50, sockets=["LGA1700", "AM5"], potencia_enfriamiento_w=130),
                   _pieza("COOLER 95W", 20, sockets=["LGA1700"], potencia_enfriamiento_w=95)],   # no cubre 117 W
    }


def test_los_armados_al_azar_son_compatibles():
    azar = random.Random(1)
    vistos = set()
    for _ in range(200):
        armado = armar(_catalogo(), CRITERIOS["media"], azar)
        if armado is None:
            continue   # combinación imposible (32 GB con módulos DDR4 de 8 en dos ranuras): se descarta
        codigos = {componente: producto["codigo"] for componente, (producto, _) in armado.items()}
        vistos.add(codigos["cpu"])
        cpu, placa, (ram, cantidad) = armado["cpu"][0], armado["motherboard"][0], armado["ram"]
        assert placa["socket"] == cpu["socket"] and cpu["generacion"] in placa["generaciones"]
        assert ram["tipo"] == placa["tipo_ram"] and ram["formato_modulo"] == "DIMM" and cantidad <= 2
        assert codigos["disco"] == "NVME 1TB" and codigos["gpu"] == "PL.VIDEO GF RTX5050"
        assert codigos["fuente"] == "FTE 600W" and codigos["gabinete"] == "GAB MATX"
        if cpu["incluye_cooler"] == "no":
            assert codigos["cooler"] == "COOLER 130W"     # el de 95 W no cubre el consumo máximo
        else:
            assert "cooler" not in codigos                 # en gama media se usa el que trae el procesador
    assert len(vistos) == 2   # salieron las dos plataformas


def test_los_porcentajes_de_cada_armado_suman_cien():
    resultado = medir(_catalogo(), muestras=300, semilla=3)["media"]
    assert 150 < resultado["armados"] <= 300   # las combinaciones imposibles se descartan
    # La mediana por componente no tiene por qué sumar 100, pero queda cerca; cada valor es un porcentaje.
    medianas = [resultado["componentes"][c]["mediana"] for c in COMPONENTES]
    assert all(0 <= m <= 100 for m in medianas) and 85 <= sum(medianas) <= 115
    for m in resultado["componentes"].values():
        assert m["p25"] <= m["mediana"] <= m["p75"]


def test_una_gama_sin_productos_se_informa_y_no_rompe():
    resultado = medir(_catalogo(), muestras=50)
    assert resultado["premium"] == {"armados": 0}     # el catálogo mínimo no tiene Ryzen 9 ni Ultra 9
    texto = documento(resultado, productos=20, solo_con_stock=False)
    assert "no se pudo armar ninguna PC de esta gama" in texto
    assert "- Gama media, placa de video:" in texto and "**Fuente:**" in texto


def test_el_disco_secundario_solo_entra_si_el_criterio_lo_pide_y_hay_puerto_sata():
    """Problema 13: gama alta y premium llevan un SSD 2,5" o HDD además del principal."""
    piezas = _catalogo()
    for placa in piezas["motherboard"]:
        placa["puertos_sata"] = 4
    piezas["almacenamiento"].append(_pieza("HDD 1TB SATA", 60, tipo="HDD", capacidad_gb=1000, conexion="SATA"))
    con_secundario = {**CRITERIOS["media"], "disco_extra": {"discos": ["SSD SATA", "HDD"], "gb": (1000, 2000)}}
    armados = [a for a in (armar(piezas, con_secundario, random.Random(i)) for i in range(200)) if a]
    assert armados, "con puerto SATA y disco SATA tiene que haber armados"
    assert all(a["disco_extra"][0]["conexion"] == "SATA" for a in armados)
    sin_secundario = [a for a in (armar(piezas, CRITERIOS["media"], random.Random(i)) for i in range(50)) if a]
    assert sin_secundario and all("disco_extra" not in a for a in sin_secundario)

    for placa in piezas["motherboard"]:
        placa["puertos_sata"] = 0
    assert all(armar(piezas, con_secundario, random.Random(i)) is None for i in range(50))
