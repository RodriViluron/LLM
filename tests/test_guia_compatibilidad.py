"""La guía de compatibilidad del RAG dice lo mismo que las reglas del código."""

from mcp_tienda.armado.guia_compatibilidad import (MARCA_FIN, MARCA_INICIO, NOMBRES_REGLAS, RUTA_DOCUMENTO,
                                                   bloque_de_numeros, escribir_en_documento)
from mcp_tienda.armado.reglas import REGLAS_AVISO, verificar_compatibilidad
from mcp_tienda.modelos import Configuracion, Producto


def _producto(categoria: str, **atributos) -> Producto:
    return Producto(codigo=categoria.upper(), nombre=categoria, categoria=categoria, categoria_origen=categoria,
                    precio=1, stock=1, atributos=atributos)


def test_el_documento_tiene_el_bloque_generado_al_dia():
    texto = RUTA_DOCUMENTO.read_text(encoding="utf-8")
    assert bloque_de_numeros() in texto, "regenerá: uv run python -m mcp_tienda.armado.guia_compatibilidad --escribir-doc"


def test_todas_las_reglas_tienen_nombre_y_su_criticidad_coincide():
    # Un armado con todas las piezas, para que se evalúen todas las reglas.
    piezas = {c: _producto(c) for c in ("cpu", "motherboard", "ram", "gpu", "almacenamiento", "fuente",
                                         "gabinete", "cooler")}
    reporte = verificar_compatibilidad(Configuracion(componentes=piezas))
    assert {r.regla for r in reporte.resultados} == set(NOMBRES_REGLAS)
    assert {r.regla for r in reporte.resultados if not r.critica} == set(REGLAS_AVISO)


def test_escribir_reemplaza_solo_el_bloque(tmp_path):
    ruta = tmp_path / "guia.md"
    ruta.write_text(f"# Guía\n\nTexto a mano.\n\n{MARCA_INICIO}\nviejo\n{MARCA_FIN}\n\nFinal.\n", encoding="utf-8")
    escribir_en_documento(ruta)
    texto = ruta.read_text(encoding="utf-8")
    assert "Texto a mano." in texto and "Final." in texto and "viejo" not in texto
    assert bloque_de_numeros() in texto
