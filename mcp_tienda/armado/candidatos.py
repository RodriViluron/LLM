"""Filtros para buscar solo candidatos compatibles con lo que ya está elegido.

Es la otra cara de las reglas de `reglas.py`: en vez de verificar un armado terminado, traduce
lo ya elegido a filtros de búsqueda. Así el modelo (o el botón «Cambiar») elige entre productos
que ya se sabe que encajan, y no tiene que razonar la compatibilidad.

Dos cuidados:
- Filtrar por un atributo deja afuera los productos que no lo informan (en SQL, `NULL <= 360` no
  es verdadero). Por eso solo se filtra por atributos que el catálogo informa bien; por ejemplo,
  nunca por `gpu.consumo_w`, que el catálogo real no trae. Lo que queda afuera por falta de dato
  lo cuenta `buscar_productos` y se le avisa al usuario.
- Estos filtros son un primer recorte. El servidor además pasa cada candidato por las reglas
  (`descarta_por_reglas`), así el filtro y la regla nunca dicen cosas distintas.

Si a una pieza elegida le falta el dato, esa restricción no se puede aplicar: se avisa en `notas`
y la verificación final dirá «sin datos».
"""

import math

from mcp_tienda.armado.reglas import (CONSUMO_BASE_W, FORMATO_MODULO_PC, MARGEN_FUENTE, consumo_cpu,
                                      fuente_del_armado, potencia_requerida, verificar_compatibilidad)
from mcp_tienda.modelos import Configuracion, Producto


def filtros_compatibles(
    categoria: str, componentes: dict[str, Producto], margen: float = MARGEN_FUENTE,
    lugar: str | None = None, cantidades: dict[str, int] | None = None,
) -> tuple[dict, list[str]]:
    """Devuelve (filtros de atributos, notas) para buscar un producto de `categoria`.

    `lugar` es el lugar del armado que se va a llenar (por defecto, el de la categoría; el segundo
    disco es `almacenamiento_extra`). La pieza que hoy ocupa ese lugar se ignora: es la que se va a
    reemplazar. `cantidades` son las unidades por lugar (si falta, 1).
    """
    lugar = lugar or categoria
    cantidades = cantidades or {}
    otros = {slot: p for slot, p in componentes.items() if slot != lugar}
    filtros: dict = {}
    notas: list[str] = []

    def dato(slot: str, atributo: str):
        """Valor del atributo de una pieza elegida; None si no está elegida o no informa el dato."""
        if slot not in otros:
            return None
        valor = otros[slot].atributos.get(atributo)
        if valor is None:
            notas.append(f"{otros[slot].codigo} ({slot}) no informa '{atributo}': no se pudo filtrar por eso")
        return valor

    def potencia_de_la_fuente() -> int | None:
        fuente = fuente_del_armado(Configuracion(componentes=otros))
        if fuente is None:
            return None
        if fuente[1] is None:
            notas.append(f"La fuente ({fuente[0]}) no informa su potencia: no se pudo filtrar por consumo")
        return fuente[1]

    if categoria == "cpu":
        if (socket := dato("motherboard", "socket")) is not None:
            filtros["socket"] = socket
        if (generaciones := dato("motherboard", "generaciones")) is not None:
            filtros["generacion__en"] = generaciones
        if (sockets := dato("cooler", "sockets")) is not None:
            filtros["socket__en"] = sockets
        maximos = []
        if (disipa := dato("cooler", "potencia_enfriamiento_w")) is not None:
            maximos.append(disipa)
        if (potencia := potencia_de_la_fuente()) is not None:
            # Lo que queda para la CPU: la fuente sin margen, menos el resto y la GPU (si se conoce).
            gpu = otros.get("gpu")
            consumo_gpu = gpu.atributos.get("consumo_w") if gpu else 0
            if consumo_gpu is not None:
                maximos.append(potencia / (1 + margen) - CONSUMO_BASE_W - consumo_gpu)
        if maximos:
            filtros["consumo_max_w__max"] = math.floor(min(maximos))

    elif categoria == "motherboard":
        if (socket := dato("cpu", "socket")) is not None:
            filtros["socket"] = socket
        if (generacion := dato("cpu", "generacion")) is not None:
            filtros["generaciones"] = generacion   # lista: «contiene»
        if (tipo := dato("ram", "tipo")) is not None:
            filtros["tipo_ram"] = tipo
        if (formatos := dato("gabinete", "formatos_admitidos")) is not None:
            filtros["formato__en"] = formatos
        if "ram" in otros and (modulos := dato("ram", "modulos")) is not None:
            filtros["ranuras_ram__min"] = modulos * cantidades.get("ram", 1)
        discos = _discos_por_conexion(otros, cantidades)
        if discos["M.2"]:
            filtros["ranuras_m2__min"] = discos["M.2"]
        if discos["SATA"]:
            filtros["puertos_sata__min"] = discos["SATA"]

    elif categoria == "ram":
        filtros["formato_modulo"] = FORMATO_MODULO_PC   # en una PC de escritorio, siempre
        if (tipo := dato("motherboard", "tipo_ram")) is not None:
            filtros["tipo"] = tipo
        if (ranuras := dato("motherboard", "ranuras_ram")) is not None:
            filtros["modulos__max"] = ranuras // cantidades.get("ram", 1)

    elif categoria == "almacenamiento":
        # Si un tipo de conexión ya no tiene lugar libre en la placa, se busca solo del otro.
        m2, sata = dato("motherboard", "ranuras_m2"), dato("motherboard", "puertos_sata")
        if m2 is not None and sata is not None:
            usados = _discos_por_conexion(otros, cantidades)
            pedidos = cantidades.get(lugar, 1)
            entra_m2, entra_sata = m2 - usados["M.2"] >= pedidos, sata - usados["SATA"] >= pedidos
            if entra_m2 != entra_sata:
                filtros["conexion"] = "M.2" if entra_m2 else "SATA"

    elif categoria == "gpu":
        if (largo := dato("gabinete", "largo_max_gpu_mm")) is not None:
            filtros["largo_mm__max"] = largo
        if (potencia := potencia_de_la_fuente()) is not None:
            filtros["fuente_recomendada_w__max"] = potencia

    elif categoria == "fuente":
        if "cpu" in otros:
            requerido, _, faltan = potencia_requerida(Configuracion(componentes=otros), margen)
            if requerido is not None:
                filtros["potencia_w__min"] = math.ceil(requerido)
            for slot, atributo in faltan:
                notas.append(f"{otros[slot].codigo} ({slot}) no informa '{atributo}': "
                             "no se pudo calcular la potencia necesaria")

    elif categoria == "gabinete":
        if (formato := dato("motherboard", "formato")) is not None:
            filtros["formatos_admitidos"] = formato
        if "gpu" in otros and otros["gpu"].atributos.get("largo_mm") is not None:
            filtros["largo_max_gpu_mm__min"] = otros["gpu"].atributos["largo_mm"]

    elif categoria == "cooler":
        if (socket := dato("cpu", "socket")) is not None:
            filtros["sockets"] = socket
        if "cpu" in otros and (consumo := consumo_cpu(otros["cpu"].atributos)) is not None:
            filtros["potencia_enfriamiento_w__min"] = consumo

    return filtros, list(dict.fromkeys(notas))


def _discos_por_conexion(piezas: dict[str, Producto], cantidades: dict[str, int]) -> dict[str, int]:
    """Cuántos discos de cada conexión (M.2 / SATA) ya hay entre las piezas elegidas."""
    cuenta = {"M.2": 0, "SATA": 0}
    for lugar in ("almacenamiento", "almacenamiento_extra"):
        if lugar in piezas and (conexion := piezas[lugar].atributos.get("conexion")) in cuenta:
            cuenta[conexion] += cantidades.get(lugar, 1)
    return cuenta


def descarta_por_reglas(categoria: str, componentes: dict[str, Producto], candidato: Producto,
                        lugar: str | None = None, cantidades: dict[str, int] | None = None) -> bool:
    """True si poner `candidato` en `lugar` hace que alguna regla dé «no cumple»."""
    lugar = lugar or categoria
    prueba = {**{s: p for s, p in componentes.items() if s != lugar}, lugar: candidato}
    cantidades = {s: n for s, n in (cantidades or {}).items() if s in prueba}
    reporte = verificar_compatibilidad(Configuracion(componentes=prueba, cantidades=cantidades))
    return any(r.estado == "no_cumple" for r in reporte.resultados)
