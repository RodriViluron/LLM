"""Operaciones sobre la configuración de PC.

Las usan dos caminos distintos, y por eso viven acá y no dentro de una tool:
- tools.py: cuando el usuario lo pide por chat («cambiá la placa de video»), la tool llama a estas
  funciones y guarda el resultado en el estado con Command(update={"configuracion": ...});
- app.py: cuando el usuario hace clic en «Cambiar», la interfaz llama a las mismas funciones y
  guarda el resultado con update_state.
Así un clic y un mensaje terminan en la misma operación.

La configuración es un diccionario (se guarda en el estado del agente y lo persiste el checkpointer):

    {"version": 3, "ultimos_cambios": ["gpu"],
     "presupuesto": 1200000, "perfil_uso": "juegos 1080p",
     "componentes": {"cpu": {...producto completo...}, "gpu": {...}},
     "cantidades": {"ram": 2},                 # unidades por lugar; si falta, 1
     "reporte": {"estado_general": "compatible", "resultados": [...]},   # None = sin verificar
     "total": 1013000.0}

Acá no se calcula nada «a ojo»: los productos, la compatibilidad y el total se le piden siempre al
servidor MCP de la tienda. El modelo solo aporta el lugar y el código del producto.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from mcp_tienda.armado.gamas import COMPONENTES_CON_GAMA
from mcp_tienda.armado.reglas import lugares_obligatorios
from mcp_tienda.cliente import ClienteTienda
from mcp_tienda.config import DIR_DATOS
from mcp_tienda.modelos import CANTIDAD_MAXIMA, LUGARES_CON_CANTIDAD, SLOTS, categoria_de_lugar

TOPE_ITERACIONES = 8

# Al abaratar, estas piezas no pueden perder capacidad (las CPU y GPU no pueden cambiar de gama).
ATRIBUTOS_A_MANTENER = {
    "ram": {"tipo": "tipo", "capacidad_gb": "capacidad_gb__min"},
    "almacenamiento": {"tipo": "tipo", "capacidad_gb": "capacidad_gb__min"},
    "almacenamiento_extra": {"tipo": "tipo", "capacidad_gb": "capacidad_gb__min"},
}


class ErrorArmado(ValueError):
    """La operación no se pudo hacer; el mensaje se le devuelve al modelo o se muestra en la interfaz."""


# --- Estado -----------------------------------------------------------------------

def nueva(presupuesto: float | None = None, perfil_uso: str | None = None) -> dict:
    return {"version": 1, "ultimos_cambios": ["presupuesto", "perfil_uso"], "presupuesto": presupuesto,
            "perfil_uso": perfil_uso, "componentes": {}, "cantidades": {}, "reporte": None, "total": 0.0}


def _avanzar(anterior: dict | None, nueva_config: dict, cambios: list[str]) -> dict:
    """Marca `nueva_config` como la versión siguiente a `anterior` y anota qué cambió."""
    return {**nueva_config, "version": (anterior or {}).get("version", 0) + 1, "ultimos_cambios": cambios}


def fusionar(actual: dict | None, propuesta: dict) -> dict:
    """Reducer del estado: decide qué queda cuando llega una configuración nueva.

    Caso normal (una operación después de otra): la propuesta es la versión siguiente → reemplaza.

    Caso «varias a la vez»: el modelo pidió agregar dos piezas en el mismo mensaje. Las dos tools
    partieron de la misma configuración, así que la segunda propuesta no conoce el cambio de la
    primera. En vez de perderlo, se aplican solo los cambios de la segunda sobre lo que ya hay.
    La compatibilidad queda «sin verificar» (reporte None) hasta la próxima verificación.
    """
    if not actual or propuesta.get("version", 0) == actual.get("version", 0) + 1:
        return propuesta
    componentes = dict(actual.get("componentes", {}))
    unidades = dict(actual.get("cantidades") or {})
    fusionada = dict(actual)
    for cambio in propuesta.get("ultimos_cambios", []):
        if cambio in ("presupuesto", "perfil_uso"):
            fusionada[cambio] = propuesta.get(cambio)
        elif cambio in propuesta.get("componentes", {}):
            componentes[cambio] = propuesta["componentes"][cambio]
            unidades[cambio] = (propuesta.get("cantidades") or {}).get(cambio, 1)
        else:
            componentes.pop(cambio, None)
            unidades.pop(cambio, None)
    unidades = {s: n for s, n in unidades.items() if s in componentes and n != 1}
    fusionada.update(
        componentes=componentes,
        cantidades=unidades,
        reporte=None,
        total=round(sum(p["precio"] * unidades.get(s, 1) for s, p in componentes.items()), 2),
        version=actual.get("version", 0) + 1,
        ultimos_cambios=sorted({*actual.get("ultimos_cambios", []), *propuesta.get("ultimos_cambios", [])}),
    )
    return fusionada


def codigos(config: dict) -> dict[str, str]:
    return {slot: producto["codigo"] for slot, producto in config.get("componentes", {}).items()}


def cantidades(config: dict) -> dict[str, int]:
    """Unidades de los lugares que llevan más de una (los demás llevan 1)."""
    componentes = config.get("componentes", {})
    return {s: n for s, n in (config.get("cantidades") or {}).items() if s in componentes and n != 1}


def cantidad(config: dict, lugar: str) -> int:
    return (config.get("cantidades") or {}).get(lugar, 1)


def obligatorios(config: dict) -> list[str]:
    """Lugares que tiene que tener este armado (dependen de lo elegido: ver reglas.lugares_obligatorios)."""
    return lugares_obligatorios({s: p.get("atributos", {}) for s, p in config.get("componentes", {}).items()})


def faltantes(config: dict) -> list[str]:
    componentes = config.get("componentes", {})
    return [s for s in obligatorios(config) if s not in componentes]


# --- Operaciones ------------------------------------------------------------------

def verificar(config: dict, cliente: ClienteTienda) -> dict:
    """Copia de la configuración con productos frescos, reporte de compatibilidad y total del servidor."""
    elegidos = codigos(config)
    if not elegidos:
        return {**config, "componentes": {}, "reporte": None, "total": 0.0}
    reporte, datos = cliente.llamar_json("verificar_compatibilidad", **elegidos,
                                         cantidades=cantidades(config) or None)
    if "error" in reporte:
        raise ErrorArmado(reporte["error"])
    return {
        **config,
        "componentes": datos["componentes"],   # precio y stock recién leídos del catálogo
        "cantidades": cantidades(config),
        "reporte": {"estado_general": reporte["estado_general"], "resultados": reporte["resultados"],
                    "avisos": reporte.get("avisos", [])},
        "total": reporte["total"],
    }


def asegurar_verificada(config: dict, cliente: ClienteTienda) -> dict:
    """Si la configuración quedó sin verificar (ver `fusionar`), la verifica y avanza la versión."""
    if config.get("componentes") and config.get("reporte") is None:
        return _avanzar(config, verificar(config, cliente), [])
    return config


def poner_componente(config: dict | None, lugar: str, codigo: str, cliente: ClienteTienda,
                     cantidad: int = 1) -> dict:
    """Agrega o reemplaza la pieza de un lugar. Devuelve la configuración nueva, ya verificada.

    `cantidad` son las unidades (por ejemplo, dos módulos de RAM iguales). Solo la RAM y los discos
    llevan más de una.
    """
    config = config or nueva()
    if lugar not in SLOTS:
        raise ErrorArmado(f"'{lugar}' no es un lugar del armado. Lugares: {', '.join(SLOTS)}")
    if cantidad != 1 and lugar not in LUGARES_CON_CANTIDAD:
        raise ErrorArmado(f"El lugar '{lugar}' lleva una sola unidad; solo ram y discos admiten cantidad")
    if not 1 <= cantidad <= CANTIDAD_MAXIMA:
        raise ErrorArmado(f"La cantidad tiene que ser de 1 a {CANTIDAD_MAXIMA}")
    respuesta, datos = cliente.llamar_json("obtener_producto", codigo=codigo)
    if "error" in respuesta:
        raise ErrorArmado(respuesta["error"])
    producto = datos["producto"]
    if producto["categoria"] != categoria_de_lugar(lugar):
        raise ErrorArmado(f"El producto {codigo} es de categoría '{producto['categoria']}' "
                          f"y no puede ir en el lugar '{lugar}'")
    borrador = {**config, "componentes": {**config.get("componentes", {}), lugar: producto},
                "cantidades": {**(config.get("cantidades") or {}), lugar: cantidad}}
    return _avanzar(config, verificar(borrador, cliente), [lugar])


def quitar_componente(config: dict, lugar: str, cliente: ClienteTienda) -> dict:
    componentes = {s: p for s, p in config.get("componentes", {}).items() if s != lugar}
    resto = {s: n for s, n in (config.get("cantidades") or {}).items() if s != lugar}
    return _avanzar(config, verificar({**config, "componentes": componentes, "cantidades": resto}, cliente),
                    [lugar])


def alternativas(config: dict, lugar: str, cliente: ClienteTienda, limite: int = 6) -> list[dict]:
    """Productos que pueden ir en `lugar` y son compatibles con el resto (lo usa el botón «Cambiar»)."""
    _, datos = cliente.llamar_json("buscar_productos", categoria=categoria_de_lugar(lugar),
                                   compatible_con=codigos(config) or None, para_lugar=lugar,
                                   cantidades=cantidades(config) or None, limite=limite + 1)
    actual = config.get("componentes", {}).get(lugar, {}).get("codigo")
    return [p for p in (datos or {}).get("productos", []) if p["codigo"] != actual][:limite]


def _incumplidas(config: dict) -> set[str]:
    resultados = (config.get("reporte") or {}).get("resultados", [])
    return {r["regla"] for r in resultados if r["estado"] == "no_cumple"}


def _resumen_producto(producto: dict) -> dict:
    return {"codigo": producto["codigo"], "nombre": producto["nombre"], "precio": producto["precio"]}


def ajustar_presupuesto(config: dict, cliente: ClienteTienda, tope: int = TOPE_ITERACIONES) -> tuple[dict, dict]:
    """Abarata la configuración hasta entrar en el presupuesto. Devuelve (configuración, informe).

    En cada vuelta cambia UNA pieza por otra más barata que:
    - sea compatible con el resto (lo filtra el servidor),
    - sea de la misma gama si es CPU o GPU, y no pierda capacidad si es RAM o disco.
    Si un solo cambio alcanza, elige el que menos resigna; si no, el que más ahorra, y sigue.
    Corta al llegar al presupuesto, al quedarse sin reemplazos o al llegar al tope de vueltas.
    """
    presupuesto = config.get("presupuesto")
    if presupuesto is None:
        raise ErrorArmado("La configuración no tiene presupuesto: indicalo con iniciar_configuracion")
    actual = verificar(config, cliente)
    cambios: list[dict] = []
    sin_gama: set[str] = set()
    descartados: set[tuple[str, str]] = set()
    vueltas = 0
    motivo = None

    while actual["total"] > presupuesto:
        if vueltas >= tope:
            motivo = f"se llegó al tope de {tope} vueltas"
            break
        vueltas += 1
        exceso = actual["total"] - presupuesto
        opciones = []
        for lugar, producto in actual["componentes"].items():
            gama = None
            if lugar in COMPONENTES_CON_GAMA:
                gama = producto.get("gama")
                if gama is None:
                    sin_gama.add(lugar)   # sin datos de gama no se reemplaza: no se puede asegurar «misma gama»
                    continue
            mantener = {filtro: producto["atributos"][atributo]
                        for atributo, filtro in ATRIBUTOS_A_MANTENER.get(lugar, {}).items()
                        if producto["atributos"].get(atributo) is not None}
            respuesta, datos = cliente.llamar_json(
                "buscar_productos", categoria=categoria_de_lugar(lugar), compatible_con=codigos(actual),
                para_lugar=lugar, cantidades=cantidades(actual) or None, gama=gama,
                atributos=mantener or None, precio_max=producto["precio"] - 0.01, limite=20)
            if "error" in respuesta:
                continue
            unidades = cantidad(actual, lugar)
            opciones += [((producto["precio"] - candidato["precio"]) * unidades, lugar, candidato)
                         for candidato in datos["productos"] if (lugar, candidato["codigo"]) not in descartados]
        if not opciones:
            motivo = "no quedan reemplazos más baratos de la misma gama y compatibles"
            break
        alcanzan = [o for o in opciones if o[0] >= exceso]
        ahorro, lugar, candidato = (min(alcanzan, key=lambda o: o[0]) if alcanzan
                                    else max(opciones, key=lambda o: o[0]))
        borrador = verificar({**actual, "componentes": {**actual["componentes"], lugar: candidato}}, cliente)
        if _incumplidas(borrador) - _incumplidas(actual):
            descartados.add((lugar, candidato["codigo"]))   # no debería pasar; por las dudas, no se acepta
            continue
        cambios.append({"lugar": lugar, "antes": _resumen_producto(actual["componentes"][lugar]),
                        "despues": _resumen_producto(candidato), "ahorro": ahorro})
        actual = borrador

    dentro = actual["total"] <= presupuesto
    informe = {"dentro_del_presupuesto": dentro, "presupuesto": presupuesto, "total": actual["total"],
               "vueltas": vueltas, "tope": tope, "cambios": cambios}
    if not dentro:
        informe["falta_ahorrar"] = round(actual["total"] - presupuesto, 2)
        informe["motivo"] = motivo
    if sin_gama:
        informe["sin_datos_de_gama"] = sorted(sin_gama)
        informe["nota"] = (f"No se reemplazaron {', '.join(sorted(sin_gama))}: no están en la tabla de gamas "
                           "y no se puede asegurar que el reemplazo sea de la misma gama.")
    return _avanzar(config, actual, [c["lugar"] for c in cambios]), informe


# --- Confirmar el pedido (solo desde la interfaz, nunca desde una tool) --------------

class PedidosLocales:
    """Destino del pedido en el escenario B: se guarda en una base local.

    Cuando la tienda defina qué es «Confirmar» (carrito o aviso al vendedor), se escribe otra clase
    con el mismo método `enviar` y se cambia acá.
    """

    def __init__(self, ruta: Path | None = None):
        self.ruta = Path(ruta or DIR_DATOS / "pedidos.sqlite")

    def _conectar(self) -> sqlite3.Connection:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.ruta)
        conn.execute("CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, "
                     "referencia TEXT, total REAL, codigos TEXT, configuracion TEXT)")
        return conn

    def enviar(self, config: dict, referencia: str = "") -> str:
        with self._conectar() as conn:
            cursor = conn.execute(
                "INSERT INTO pedidos (fecha, referencia, total, codigos, configuracion) VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), referencia, config["total"],
                 json.dumps(codigos(config)), json.dumps(config, ensure_ascii=False)))
            return f"P-{cursor.lastrowid:05d}"

    def listar(self) -> list[dict]:
        with self._conectar() as conn:
            filas = conn.execute("SELECT id, fecha, referencia, total, codigos FROM pedidos ORDER BY id").fetchall()
        return [{"id": f"P-{f[0]:05d}", "fecha": f[1], "referencia": f[2], "total": f[3], "codigos": json.loads(f[4])}
                for f in filas]


def motivos_para_no_confirmar(config: dict) -> list[str]:
    """Por qué todavía no se puede confirmar (lista vacía = se puede).

    Bloquea: piezas obligatorias que faltan, cualquier «no cumple» y los «sin datos» de reglas
    críticas (sin el dato no se sabe si la PC funciona). Los «sin datos» no críticos no bloquean.
    """
    motivos = []
    componentes = config.get("componentes", {})
    if faltan := faltantes(config):
        motivos.append(f"Faltan piezas: {', '.join(faltan)}")
    for regla in (config.get("reporte") or {}).get("resultados", []):
        if regla["estado"] == "no_cumple":
            motivos.append(f"Incompatible: {regla['detalle']}")
        elif regla["estado"] == "sin_datos" and regla.get("critica", True) \
                and not regla["detalle"].startswith("Falta elegir"):   # eso ya está en «Faltan piezas»
            motivos.append(f"Sin verificar: {regla['detalle']}")
    sin_stock = [f"{p['codigo']} ({lugar})" for lugar, p in componentes.items() if p["stock"] <= 0]
    if sin_stock:
        motivos.append(f"Sin stock: {', '.join(sin_stock)}")
    return motivos


def confirmar_pedido(config: dict, cliente: ClienteTienda, destino: PedidosLocales, referencia: str = "") -> dict:
    """Confirma el pedido que el usuario está viendo. La llama solo el botón de la interfaz.

    Antes de enviar vuelve a pedirle a la tienda precio, stock y compatibilidad. Si algo cambió
    respecto de lo que el usuario tenía en pantalla (por ejemplo, el total), NO confirma: devuelve
    la configuración actualizada para que la vea y decida de nuevo.

    Devuelve {"confirmado", "pedido", "configuracion", "motivos"}.
    """
    fresca = _avanzar(config, verificar(config, cliente), [])
    motivos = motivos_para_no_confirmar(fresca)
    if fresca["total"] != config.get("total"):
        motivos.append(f"El total cambió de {config.get('total')} a {fresca['total']}: revisalo y confirmá de nuevo")
    if motivos:
        return {"confirmado": False, "pedido": None, "configuracion": fresca, "motivos": motivos}
    return {"confirmado": True, "pedido": destino.enviar(fresca, referencia), "configuracion": fresca, "motivos": []}


# --- Lo que lee el modelo -----------------------------------------------------------

def resumen(config: dict) -> dict:
    """Versión corta de la configuración para devolverle al modelo (los datos completos van a la interfaz)."""
    componentes = {}
    for lugar, producto in config.get("componentes", {}).items():
        componentes[lugar] = {**_resumen_producto(producto), "stock": producto["stock"]}
        if (n := cantidad(config, lugar)) != 1:
            componentes[lugar]["cantidad"] = n
        if lugar in COMPONENTES_CON_GAMA:
            componentes[lugar]["gama"] = producto.get("gama") or "sin datos"
    reporte = config.get("reporte")
    datos = {
        "presupuesto": config.get("presupuesto"),
        "perfil_uso": config.get("perfil_uso"),
        "componentes": componentes,
        "faltan": faltantes(config),
        "sin_stock": [s for s, c in componentes.items() if c["stock"] <= 0],
        "total": config.get("total", 0.0),
        "compatibilidad": reporte["estado_general"] if reporte else "sin_verificar",
        "reglas_a_revisar": [r for r in (reporte or {}).get("resultados", []) if r["estado"] != "cumple"],
    }
    if config.get("presupuesto") is not None:
        datos["dentro_del_presupuesto"] = datos["total"] <= config["presupuesto"]
        if not datos["dentro_del_presupuesto"]:
            datos["excedente"] = round(datos["total"] - config["presupuesto"], 2)
    return datos
