"""Presupuesto en PDF al confirmar un armado (problema 34).

Genera los datos estructurados desde la configuración verificada por `armado.py` (precios,
cantidades, total y avisos de compatibilidad reales) y los vuelca a PDF con `fpdf2` sin
depender del modelo de lenguaje.
"""

from datetime import date, datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

import armado
from mcp_tienda.modelos import SLOTS

TITULO = "Todo Computación — Presupuesto de PC"
LEYENDA = "Presupuesto de referencia: precios y stock sujetos a cambio. No incluye pago."

NOMBRES_LUGAR = {
    "cpu": "Procesador",
    "cooler": "Cooler",
    "motherboard": "Motherboard",
    "ram": "Memoria RAM",
    "almacenamiento": "Almacenamiento",
    "almacenamiento_extra": "Segundo disco",
    "gpu": "Placa de video",
    "gabinete": "Gabinete",
    "fuente": "Fuente",
}

_REEMPLAZOS_LATIN1 = {
    "—": "-",
    "–": "-",
    "…": "...",
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "•": "-",
    "€": "EUR",
}


def _texto_latin1(texto: object) -> str:
    """Convierte texto Unicode a Latin-1 conservando tildes y ñ para las fuentes core de fpdf2."""
    limpio = " ".join(str(texto).split())
    for origen, destino in _REEMPLAZOS_LATIN1.items():
        limpio = limpio.replace(origen, destino)
    return limpio.encode("latin-1", "replace").decode("latin-1")


def _pesos(valor: float | int) -> str:
    return f"$ {valor:,.0f}".replace(",", ".")


def _fecha_texto(fecha: date | datetime | str | None) -> str:
    if fecha is None:
        return date.today().isoformat()
    if isinstance(fecha, datetime):
        return fecha.date().isoformat()
    if isinstance(fecha, date):
        return fecha.isoformat()
    return str(fecha)


def datos_del_presupuesto(config: dict, referencia: str, fecha: date | datetime | str | None = None) -> dict:
    """Arma el diccionario de presupuesto desde una configuración verificada de `armado.py`.

    Incluye filas ordenadas por lugar (con cantidad y subtotal), total sumado de los subtotales,
    avisos de compatibilidad (incluidos los «sin datos») y la leyenda fija.
    """
    componentes = config.get("componentes") or {}
    orden = [lugar for lugar in SLOTS if lugar in componentes]
    orden += [lugar for lugar in componentes if lugar not in orden]

    filas = []
    for lugar in orden:
        producto = componentes[lugar]
        cantidad = armado.cantidad(config, lugar)
        precio_unitario = float(producto.get("precio") or 0.0)
        subtotal = round(precio_unitario * cantidad, 2)
        filas.append({
            "lugar": lugar,
            "nombre_lugar": NOMBRES_LUGAR.get(lugar, lugar),
            "codigo": str(producto.get("codigo", "")),
            "nombre": " ".join(str(producto.get("nombre", "")).split()),
            "cantidad": cantidad,
            "precio_unitario": precio_unitario,
            "subtotal": subtotal,
        })

    total = round(sum(fila["subtotal"] for fila in filas), 2)
    reporte = config.get("reporte") or {}
    avisos: list[str] = []
    for regla in reporte.get("resultados", []):
        estado = regla.get("estado")
        if estado == "cumple":
            continue
        prefijo = ("No es compatible" if estado == "no_cumple"
                   else "Sin datos" if regla.get("critica", True)
                   else "Aviso (sin datos)")
        mensaje = f"{prefijo}: {regla.get('detalle', '')}".strip()
        if mensaje not in avisos:
            avisos.append(mensaje)
    for aviso in reporte.get("avisos", []) or []:
        if aviso and aviso not in avisos:
            avisos.append(aviso)

    return {
        "titulo": TITULO,
        "referencia": str(referencia),
        "fecha": _fecha_texto(fecha),
        "perfil_uso": config.get("perfil_uso"),
        "presupuesto": config.get("presupuesto"),
        "estado_compatibilidad": reporte.get("estado_general", "sin_verificar"),
        "filas": filas,
        "total": total,
        "avisos": avisos,
        "leyenda": LEYENDA,
    }


def pdf_del_presupuesto(datos: dict) -> bytes:
    """Genera el PDF del presupuesto y devuelve sus bytes (`%PDF-...`)."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    ancho_util = pdf.w - pdf.l_margin - pdf.r_margin

    # Encabezado
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(ancho_util, 9, _texto_latin1(datos.get("titulo", TITULO)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(70, 70, 70)
    meta = f"Referencia: {datos.get('referencia', '')}   |   Fecha: {datos.get('fecha', '')}"
    if datos.get("perfil_uso"):
        meta += f"   |   Uso: {datos['perfil_uso']}"
    pdf.cell(ancho_util, 6, _texto_latin1(meta), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Tabla de componentes
    pdf.set_font("Helvetica", "", 9)
    anchos = (26, 22, ancho_util - (26 + 22 + 12 + 28 + 30), 12, 28, 30)
    with pdf.table(
        col_widths=anchos,
        text_align=("LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
        line_height=5.5,
        padding=1.8,
        borders_layout="HORIZONTAL_LINES",
    ) as tabla:
        cabecera = tabla.row()
        for col in ("Lugar", "Código", "Componente", "Cant.", "Unitario", "Subtotal"):
            cabecera.cell(_texto_latin1(col))
        for fila in datos.get("filas", []):
            renglon = tabla.row()
            renglon.cell(_texto_latin1(fila["nombre_lugar"]))
            renglon.cell(_texto_latin1(fila["codigo"]))
            renglon.cell(_texto_latin1(fila["nombre"]))
            renglon.cell(str(fila["cantidad"]))
            renglon.cell(_pesos(fila["precio_unitario"]))
            renglon.cell(_pesos(fila["subtotal"]))

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(ancho_util, 8, _texto_latin1(f"Total: {_pesos(datos.get('total', 0.0))}"),
             align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if datos.get("presupuesto") is not None:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(70, 70, 70)
        pdf.cell(
            ancho_util,
            5,
            _texto_latin1(f"Presupuesto indicado: {_pesos(datos['presupuesto'])}"),
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_text_color(0, 0, 0)

    # Avisos de compatibilidad (incluidos los sin datos)
    if avisos := datos.get("avisos") or []:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(ancho_util, 6, _texto_latin1("Avisos de compatibilidad"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        for aviso in avisos:
            pdf.multi_cell(ancho_util, 5, _texto_latin1(f"- {aviso}"))

    # Leyenda al pie
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(ancho_util, 5, _texto_latin1(datos.get("leyenda", LEYENDA)))
    pdf.set_text_color(0, 0, 0)

    return bytes(pdf.output())
