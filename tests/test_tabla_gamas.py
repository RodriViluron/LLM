"""Problema 1: la tabla de gamas se genera desde los criterios de gamas.md y reconoce los nombres reales.

- El normalizador entiende los nombres pegados de la tienda («RTX5060TI», «GTX1650») y los de los
  requisitos de juegos («GTX 1060»), sin confundir modelos distintos («5600» con «5600G»).
- Premium es la cuarta gama.
- El generador asigna solo lo que dicen los criterios; lo demás queda «pendiente de decidir».
- La sección manual del documento se conserva al regenerar y manda sobre lo generado.
- El filtro `gama` de buscar_productos no descarta en silencio los productos sin gama.
"""

import pytest

from mcp_tienda.armado.gamas import GAMAS, _normalizar, buscar_fila, clasificar_gama
from mcp_tienda.armado.tabla_gamas import (
    MARCA_MANUAL_FIN,
    MARCA_MANUAL_INICIO,
    armar_tabla,
    escribir_documento,
    modelo_de,
)


def _tabla(tmp_path, filas: str):
    ruta = tmp_path / "tabla.md"
    ruta.write_text("| componente | modelo | gama | puntaje |\n|---|---|---|---|\n" + filas, encoding="utf-8")
    return ruta


# --- Normalizador ------------------------------------------------------------------

@pytest.mark.parametrize("nombre, componente, modelo_esperado", [
    ("PL.VIDEO GF RTX5060TI 8G/D7/2F/OC", "gpu", "RTX 5060 Ti"),
    ("PL.VIDEO GF RTX5060 8G/D7/2F/OC", "gpu", "RTX 5060"),
    ("PL.VIDEO GF GTX1650 4G/D6/2F", "gpu", "GTX 1650"),
    ("GeForce GTX 1060 6GB", "gpu", "GTX 1060"),          # requisito de un juego, con espacio
    ("CPU INTEL CORE I5 12400F  ALDERLAKE 1700", "cpu", "Core i5-12400F"),
    ("Intel Core i5-4460", "cpu", "Core i5-4460"),
    ("CPU AMD RYZEN 5 5600           S/VID AM4", "cpu", "Ryzen 5 5600"),
    ("CPU AMD RYZEN 5 5600G                AM4", "cpu", "Ryzen 5 5600G"),
    ("CPU AMD RYZEN 7 9800X3D S/COOL       AM5", "cpu", "Ryzen 7 9800X3D"),
    ("CPU INTEL ULTRA 5 225F  ARROWLAKE   1851", "cpu", "Ultra 5 225F"),
])
def test_los_nombres_reales_coinciden_con_su_fila(tmp_path, nombre, componente, modelo_esperado):
    tabla = _tabla(tmp_path, "".join(f"| {c} | {m} | media | |\n" for c, m in [
        ("gpu", "RTX 5060 Ti"), ("gpu", "RTX 5060"), ("gpu", "GTX 1650"), ("gpu", "GTX 1060"),
        ("cpu", "Core i5-12400F"), ("cpu", "Core i5-4460"), ("cpu", "Ryzen 5 5600"), ("cpu", "Ryzen 5 5600G"),
        ("cpu", "Ryzen 7 9800X3D"), ("cpu", "Ultra 5 225F"),
    ]))
    fila = buscar_fila(nombre, componente, tabla)
    assert fila is not None, nombre
    assert fila["modelo"] == _normalizar(modelo_esperado)


def test_modelos_distintos_no_se_confunden(tmp_path):
    tabla = _tabla(tmp_path, "| cpu | Ryzen 5 5600 | media | |\n| gpu | RTX 5060 | alta | |\n"
                             "| gpu | RX 7600 XT | alta | |\n")
    assert buscar_fila("CPU AMD RYZEN 5 5600GT AM4", "cpu", tabla) is None       # 5600GT no es 5600
    assert buscar_fila("CPU AMD RYZEN 5 5600G AM4", "cpu", tabla) is None        # 5600G no es 5600
    assert buscar_fila("PL.VIDEO GF RTX5060TI 8G", "gpu", tabla) is None         # 5060 Ti no es 5060
    assert buscar_fila("PL.VIDEO RADEON RX7600 8G/D6", "gpu", tabla) is None     # 7600 no es 7600 XT


def test_premium_es_una_gama(tmp_path):
    assert GAMAS == ("baja", "media", "alta", "premium")
    tabla = _tabla(tmp_path, "| cpu | Ultra 9 285K | premium | |\n")
    assert clasificar_gama("CPU INTEL ULTRA 9 285K  ARROWLAKE   1851", "cpu", tabla) == "premium"


def test_una_fila_posterior_manda_sobre_la_anterior(tmp_path):
    """La sección manual va después de la generada: lo que corrige el grupo manda."""
    tabla = _tabla(tmp_path, "| gpu | RTX 5070 | alta | |\n| gpu | RTX 5070 | premium | |\n")
    assert clasificar_gama("PL.VIDEO GF RTX5070 12G/D7", "gpu", tabla) == "premium"


# --- Generador -------------------------------------------------------------------------

def _cpu(nombre, socket):
    return {"codigo": nombre[-6:], "nombre": nombre, "categoria": "cpu", "socket": socket}


def _gpu(nombre):
    return {"codigo": nombre[-6:], "nombre": nombre, "categoria": "gpu"}


def test_modelo_de_lee_el_modelo_del_nombre():
    assert modelo_de("PL.VIDEO GF RTX3080TI    12G/D6/3F", "gpu") == "RTX 3080 Ti"
    assert modelo_de("PL.VIDEO NV QUADRO  P620  2G/D5/1F", "gpu") == "Quadro P620"
    assert modelo_de("CPU INTEL CELERON G5900 COMETLAKE   1200", "cpu") == "Celeron G5900"
    assert modelo_de("CPU INTEL CORE 2 DUO E6550           775", "cpu") is None   # no se sabe leer: pendiente


def test_armar_tabla_asigna_solo_lo_que_dicen_los_criterios():
    productos = [
        _cpu("CPU INTEL CORE I5 12400F  ALDERLAKE 1700", "LGA1700"),     # media (i5, socket 1700)
        _cpu("CPU INTEL CORE I5 12400   ALDERLAKE 1700", "LGA1700"),     # media
        _cpu("CPU AMD RYZEN 3 3200G                AM4", "AM4"),         # baja
        _cpu("CPU INTEL CORE I5 3570K IVY BRIDGE  1155", None),          # socket viejo: pendiente
        _cpu("CPU INTEL ULTRA 7 265K  ARROWLAKE   1851", "LGA1851"),     # ningún criterio: pendiente
        _cpu("CPU INTEL ULTRA 9 285K  ARROWLAKE   1851", "LGA1851"),     # premium
        _gpu("PL.VIDEO GF RTX5050       8G/D6/2F"),                     # media
        _gpu("PL.VIDEO GF RTX5070      12G/D7/2F/OC"),                  # alta y premium: pendiente
        _gpu("PL.VIDEO GF GT1030        2G/D5/1F/LP"),                   # ningún criterio: pendiente
    ]
    filas, pendientes = armar_tabla(productos)
    asignadas = {(f["componente"], f["modelo"]): f["gama"] for f in filas}
    assert asignadas == {
        ("cpu", "Core i5-12400F"): "media", ("cpu", "Core i5-12400"): "media",
        ("cpu", "Ryzen 3 3200G"): "baja", ("cpu", "Ultra 9 285K"): "premium",
        ("gpu", "RTX 5050"): "media",
    }
    motivos = {p["modelo"]: p["motivo"] for p in pendientes}
    assert "socket" in motivos["Core i5-3570K"]
    assert "ningún criterio" in motivos["Ultra 7 265K"]
    assert "alta" in motivos["RTX 5070"] and "premium" in motivos["RTX 5070"]
    assert "ningún criterio" in motivos["GT 1030"]


def test_escribir_documento_conserva_la_seccion_manual(tmp_path):
    ruta = tmp_path / "tabla_cpu_gpu_por_gama.md"
    manual = f"{MARCA_MANUAL_INICIO}\n| gpu | GTX 1060 | media | |\n{MARCA_MANUAL_FIN}"
    ruta.write_text(f"# viejo\n\n{manual}\n\nresto viejo\n", encoding="utf-8")
    filas = [{"componente": "cpu", "modelo": "Core i5-12400F", "gama": "media", "productos": 2}]
    pendientes = [{"componente": "gpu", "modelo": "RTX 5070", "motivo": "entra en dos gamas: alta y premium"}]
    escribir_documento(ruta, filas, pendientes, fecha="2026-11-19")
    texto = ruta.read_text(encoding="utf-8")
    assert "| gpu | GTX 1060 | media | |" in texto                      # la parte manual sigue
    assert "| cpu | Core i5-12400F | media | |" in texto
    assert "RTX 5070" in texto and "dos gamas" in texto
    assert "resto viejo" not in texto                                   # lo demás se regenera
    assert texto.index("Core i5-12400F") < texto.index("GTX 1060")       # la manual va después: manda
    assert clasificar_gama("PL.VIDEO GF GTX1060 6G", "gpu", ruta) == "media"
    assert clasificar_gama("CPU INTEL CORE I5 12400F ALDERLAKE 1700", "cpu", ruta) == "media"


def test_cada_fila_generada_reconoce_a_su_producto(tmp_path):
    """Control de consistencia: lo que se escribe en la tabla lo vuelve a encontrar clasificar_gama."""
    productos = [_cpu("CPU AMD RYZEN 7 9800X3D S/COOL       AM5", "AM5"), _gpu("PL.VIDEO GF RTX5060TI     8G/D7/2F/OC")]
    filas, _ = armar_tabla(productos)
    ruta = tmp_path / "t.md"
    escribir_documento(ruta, filas, [], fecha="2026-11-19")
    for p in productos:
        assert clasificar_gama(p["nombre"], p["categoria"], ruta) is not None, p["nombre"]


# --- Filtro de buscar_productos ----------------------------------------------------------

def test_el_filtro_de_gama_no_descarta_en_silencio(cliente):
    """Sin productos de esa gama, los que no tienen gama vuelven aparte y con una nota clara."""
    # La tabla de los tests no tiene ningún procesador premium.
    respuesta, _ = cliente.llamar_json("buscar_productos", categoria="cpu", gama="premium", solo_con_stock=False)
    assert respuesta["cantidad"] == 0
    assert respuesta["productos_sin_gama"], respuesta
    assert all(p["gama"] == "sin datos" for p in respuesta["productos_sin_gama"])
    assert "no los presentes como de gama premium" in " ".join(respuesta["notas"])


def test_el_filtro_acepta_premium(cliente):
    respuesta, _ = cliente.llamar_json("buscar_productos", categoria="gpu", gama="premium", solo_con_stock=False)
    assert "error" not in respuesta
