"""Pruebas de generación del presupuesto en PDF (problema 34)."""

from datetime import date

import armado
from presupuesto_pdf import LEYENDA, TITULO, datos_del_presupuesto, pdf_del_presupuesto


def test_datos_del_presupuesto_suma_subtotales_con_cantidades_e_incluye_avisos(cliente):
    config = armado.nueva(presupuesto=2_000_000, perfil_uso="edición — ñandú ✅")
    config = armado.poner_componente(config, "cpu", "CPU002", cliente)
    config = armado.poner_componente(config, "ram", "RAM003", cliente, cantidad=2)
    config = armado.poner_componente(config, "gpu", "GPU003", cliente)
    config["reporte"]["resultados"].append({
        "regla": "largo_gpu_gabinete",
        "estado": "sin_datos",
        "detalle": "GAB004 no informa 'largo_max_gpu_mm'",
        "critica": False,
    })

    datos = datos_del_presupuesto(config, referencia="P-00001", fecha=date(2026, 11, 20))
    assert datos["titulo"] == TITULO
    assert datos["referencia"] == "P-00001"
    assert datos["fecha"] == "2026-11-20"
    assert datos["leyenda"] == LEYENDA

    fila_ram = next(f for f in datos["filas"] if f["lugar"] == "ram")
    assert fila_ram["cantidad"] == 2
    assert fila_ram["subtotal"] == round(fila_ram["precio_unitario"] * 2, 2)
    assert datos["total"] == round(sum(f["subtotal"] for f in datos["filas"]), 2)
    assert any("largo_max_gpu_mm" in a for a in datos["avisos"])

    pdf = pdf_del_presupuesto(datos)
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")
