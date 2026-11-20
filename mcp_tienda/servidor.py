"""Servidor MCP «tienda-amn»: catálogo de la tienda y reglas deterministas de compatibilidad.

Expone tres tools y nada más:
- buscar_productos y obtener_producto: consultan el catálogo local (datos/catalogo.sqlite), que se
  llena desde el catálogo de prueba o desde la API de la tienda.
- verificar_compatibilidad: aplica las reglas de armado/reglas.py y calcula el total.

No guarda estado: la configuración de PC vive en el estado del agente. Tampoco confirma pedidos.

Cada tool devuelve dos cosas (ver CallToolResult):
- un texto corto en JSON, que es lo que lee el modelo;
- `structuredContent` con los datos completos, que llega a la interfaz como `artifact`.

Se ejecuta solo (lo levanta mcp_tienda/cliente.py):  python -m mcp_tienda.servidor
"""

import json
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from mcp_tienda.armado.candidatos import descarta_por_reglas, filtros_compatibles
from mcp_tienda.armado.gamas import COMPONENTES_CON_GAMA, clasificar_gama
from mcp_tienda.armado.reglas import verificar_compatibilidad as aplicar_reglas
from mcp_tienda.catalogo import LIMITE_MAXIMO, Catalogo, FiltroInvalido
from mcp_tienda.ingesta.extraccion import SOCKETS as SOCKETS_ARMADO
from mcp_tienda.ingesta.extraccion import limpiar_texto
from mcp_tienda.modelos import SLOTS, Configuracion, Producto, categoria_de_lugar

Categoria = Literal["cpu", "motherboard", "ram", "gpu", "almacenamiento", "fuente", "gabinete",
                    "cooler", "ups", "cables", "otros"]

mcp = FastMCP("tienda-amn", log_level="WARNING")

# Filtros que se aplican solo cuando la búsqueda es para el armado (problema 33): plataformas viejas fuera.
FILTROS_DEL_ARMADO = {
    "cpu": {"socket__en": list(SOCKETS_ARMADO)},
    "motherboard": {"socket__en": list(SOCKETS_ARMADO)},
    "ram": {"formato_modulo": "DIMM", "tipo__en": ["DDR4", "DDR5"]},
}


def _resultado(para_el_modelo: dict, para_la_interfaz: dict | None = None) -> CallToolResult:
    texto = json.dumps(para_el_modelo, ensure_ascii=False)
    return CallToolResult(content=[TextContent(type="text", text=texto)],
                          structuredContent=para_la_interfaz if para_la_interfaz is not None else para_el_modelo)


def _error(mensaje: str) -> CallToolResult:
    """Los errores vuelven como dato, no como excepción: así el modelo puede corregir la llamada."""
    return _resultado({"error": mensaje})


def producto_completo(producto: Producto) -> dict:
    """El producto con todo lo que necesita una tarjeta de la interfaz."""
    datos = producto.model_dump()
    datos["descripcion"] = limpiar_texto(producto.descripcion)   # sin HTML
    if producto.categoria in COMPONENTES_CON_GAMA:
        datos["gama"] = clasificar_gama(producto.nombre, producto.categoria)   # None = sin datos
    return datos


def producto_resumido(producto: Producto) -> dict:
    """Lo que lee el modelo: sin descripción (es texto externo y largo) y con la gama por reglas."""
    datos = producto.resumen()
    if producto.categoria in COMPONENTES_CON_GAMA:
        datos["gama"] = clasificar_gama(producto.nombre, producto.categoria) or "sin datos"
    return datos


def _cargar_componentes(catalogo: Catalogo, codigos: dict[str, str | None]) -> dict[str, Producto] | str:
    """Trae del catálogo los productos de un armado. Devuelve un mensaje de error si algo no cierra."""
    componentes = {}
    for slot, codigo in codigos.items():
        if not codigo:
            continue
        if slot not in SLOTS:
            return f"'{slot}' no es un lugar del armado. Lugares: {', '.join(SLOTS)}"
        producto = catalogo.obtener(codigo)
        if producto is None:
            return f"No existe un producto con código {codigo}"
        if producto.categoria != categoria_de_lugar(slot):
            return f"El producto {codigo} es de categoría '{producto.categoria}' y no puede ir en el lugar '{slot}'"
        componentes[slot] = producto
    return componentes


@mcp.tool()
def buscar_productos(
    texto: str | None = None,
    categoria: Categoria | None = None,
    precio_max: float | None = None,
    precio_min: float | None = None,
    marca: str | None = None,
    atributos: dict[str, str | float | list[str]] | None = None,
    compatible_con: dict[str, str] | None = None,
    gama: Literal["baja", "media", "alta", "premium"] | None = None,
    solo_con_stock: bool = True,
    limite: int = 5,
    cantidades: dict[str, int] | None = None,
    para_lugar: str | None = None,
) -> CallToolResult:
    """Busca productos en el catálogo de la tienda. Combiná texto con filtros.

    Args:
        texto: palabras clave del producto, por ejemplo "hdmi" o "rtx 4060".
        categoria: categoría del producto.
        precio_max: precio máximo en pesos.
        precio_min: precio mínimo en pesos.
        marca: marca exacta, por ejemplo "Kingston".
        atributos: filtros por atributo, p. ej. {"socket": "AM4"} o {"potencia_w__min": 650}.
        compatible_con: piezas ya elegidas, como {"cpu": "CPU002", "gabinete": "GAB004"}. Con esto y
            `categoria`, devuelve solo productos compatibles con esas piezas.
        gama: baja, media, alta o premium. Solo para cpu y gpu; sale de la tabla de referencia, no se
            adivina. Si nada cumple, los productos sin gama asignada vuelven aparte en productos_sin_gama.
        solo_con_stock: si es true, solo devuelve productos con stock.
        limite: cantidad máxima de resultados (1 a 20).
        cantidades: unidades por lugar del armado, como {"ram": 2}. Opcional; si falta, 1.
        para_lugar: lugar del armado que se llena, si no es el de la categoría (el segundo disco es
            "almacenamiento_extra"). Opcional.
    """
    catalogo = Catalogo()
    if gama and categoria not in COMPONENTES_CON_GAMA:
        return _error("El filtro de gama solo aplica a las categorías cpu y gpu")
    limite = max(1, min(limite, 20))
    filtros = dict(atributos or {})
    notas: list[str] = []
    if para_lugar or compatible_con:
        # Armado: solo plataformas que el armado ofrece (problema 33). Un socket 775 o una DDR3 no entran.
        categoria_armado = categoria or (categoria_de_lugar(para_lugar) if para_lugar in SLOTS else None)
        for filtro, valor in FILTROS_DEL_ARMADO.get(categoria_armado, {}).items():
            filtros.setdefault(filtro, valor)
    if compatible_con:
        if not categoria:
            return _error("Para usar compatible_con hay que indicar la categoría que se busca")
        componentes = _cargar_componentes(catalogo, compatible_con)
        if isinstance(componentes, str):
            return _error(componentes)
        por_compatibilidad, notas = filtros_compatibles(categoria, componentes, lugar=para_lugar,
                                                        cantidades=cantidades)
        filtros.update(por_compatibilidad)
    comunes = dict(categoria=categoria, precio_min=precio_min, precio_max=precio_max, marca=marca,
                   solo_con_stock=solo_con_stock)
    try:
        # La gama no está en la base y la verificación por reglas tampoco: se filtra después de
        # buscar, así que en esos casos se traen TODOS los candidatos. Con un tope de 50 (ordenados por
        # precio) las piezas caras nunca entraban y la búsqueda por gama alta o premium volvía vacía.
        despues = bool(gama or compatible_con)
        productos = catalogo.buscar(texto=texto, atributos=filtros, limite=LIMITE_MAXIMO if despues else limite,
                                    **comunes)
        sin_dato = catalogo.contar_sin_dato(filtros, **comunes)
    except (FiltroInvalido, ValueError) as e:
        return _error(str(e))

    if compatible_con:
        # El filtro es un primer recorte; la regla decide. Así nunca se ofrece algo que la
        # verificación después marque como incompatible.
        compatibles = [p for p in productos
                       if not descarta_por_reglas(categoria, componentes, p, para_lugar, cantidades)]
        if descartados := len(productos) - len(compatibles):
            notas.append(f"{descartados} productos se descartaron porque no cumplen alguna regla de compatibilidad.")
        productos = compatibles if gama else compatibles[:limite]

    extra, extra_interfaz = {}, {}
    if gama:
        gamas = {p.codigo: clasificar_gama(p.nombre, p.categoria) for p in productos}
        sin_gama = [p for p in productos if gamas[p.codigo] is None]
        productos = [p for p in productos if gamas[p.codigo] == gama][:limite]
        if sin_gama:
            notas.append(f"{len(sin_gama)} productos no están en la tabla de gamas: no se sabe su gama.")
        if sin_gama and not productos:
            # No descartar en silencio: el modelo los ve, pero sabiendo que no tienen gama.
            extra["productos_sin_gama"] = [producto_resumido(p) for p in sin_gama[:limite]]
            extra_interfaz["productos_sin_gama"] = [producto_completo(p) for p in sin_gama[:limite]]
            notas.append(f"Ninguno tiene gama {gama}. Los que no tienen gama asignada van en productos_sin_gama: "
                         f"no los presentes como de gama {gama}; si los ofrecés, decile al usuario que su gama "
                         "no está en la tabla de referencia.")
    if sin_dato:
        extra["sin_dato"] = sin_dato
        notas.append(f"{sin_dato} productos quedaron afuera porque no informan el dato filtrado: "
                     "no se sabe si cumplen. Avisale al usuario.")
    if notas:
        extra["notas"] = notas
    return _resultado(
        {"cantidad": len(productos), "productos": [producto_resumido(p) for p in productos], **extra},
        {"productos": [producto_completo(p) for p in productos], "filtros_aplicados": filtros,
         **extra, **extra_interfaz},
    )


@mcp.tool()
def obtener_producto(codigo: str) -> CallToolResult:
    """Devuelve un producto del catálogo por su código, con sus atributos, precio, stock y descripción.

    Args:
        codigo: código del producto, por ejemplo "CAB002".
    """
    producto = Catalogo().obtener(codigo)
    if producto is None:
        return _error(f"No existe un producto con código {codigo}")
    completo = producto_completo(producto)
    resumen = producto_resumido(producto)
    # La descripción es texto externo: entra como dato, no como instrucción.
    resumen["descripcion_texto_externo"] = completo["descripcion"][:600]
    return _resultado(resumen, {"producto": completo})


@mcp.tool()
def verificar_compatibilidad(
    cpu: str | None = None,
    motherboard: str | None = None,
    ram: str | None = None,
    gpu: str | None = None,
    almacenamiento: str | None = None,
    fuente: str | None = None,
    gabinete: str | None = None,
    cooler: str | None = None,
    almacenamiento_extra: str | None = None,
    cantidades: dict[str, int] | None = None,
) -> CallToolResult:
    """Verifica con reglas fijas si un armado de PC es compatible y calcula el total.

    Args:
        cpu: código del procesador.
        motherboard: código de la motherboard.
        ram: código de la memoria RAM.
        gpu: código de la placa de video (opcional).
        almacenamiento: código del disco.
        fuente: código de la fuente.
        gabinete: código del gabinete.
        cooler: código del cooler (opcional).
        almacenamiento_extra: código del segundo disco (opcional).
        cantidades: unidades por lugar, como {"ram": 2}; solo ram y discos llevan más de una.
    """
    codigos = {"cpu": cpu, "motherboard": motherboard, "ram": ram, "gpu": gpu,
               "almacenamiento": almacenamiento, "almacenamiento_extra": almacenamiento_extra,
               "fuente": fuente, "gabinete": gabinete, "cooler": cooler}
    componentes = _cargar_componentes(Catalogo(), codigos)
    if isinstance(componentes, str):
        return _error(componentes)
    try:
        config = Configuracion(componentes=componentes,
                               cantidades={s: n for s, n in (cantidades or {}).items() if s in componentes})
    except ValidationError as e:
        return _error(e.errors()[0]["msg"].removeprefix("Value error, "))
    reporte = aplicar_reglas(config).como_dict()
    reporte["total"] = config.total
    reporte["cantidades"] = {s: config.cantidad(s) for s in componentes}
    return _resultado(
        reporte,
        {**reporte, "componentes": {slot: producto_completo(p) for slot, p in componentes.items()}},
    )


if __name__ == "__main__":
    mcp.run()   # transporte stdio
