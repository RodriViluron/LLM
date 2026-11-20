"""Prueba de punta a punta del armado con la entrevista (paso 10), con modelo local.

Igual que armado_punta_a_punta.py (paso 9g), pero el «usuario» contesta la entrevista: cada pedido
trae las respuestas que daría una persona con esa necesidad. Cuando el agente deja una pregunta
pendiente en la entrevista, se le responde con la opción de ese pedido; cuando pregunta el
presupuesto, se elige la opción que empieza con `presupuesto` (una gama). Si el agente pregunta la
gama o el uso por fuera de la entrevista, se cuenta como falla (`preguntas_de_gama`).

Métricas por corrida: entrevista completa, perfil correcto, piezas, faltantes, compatibilidad,
confirmable, dentro del presupuesto, preguntas de gama, llamadas (con error), afirmaciones sin tool.

Uso (el catálogo se elige con AMN_CATALOGO_DB):
    uv run python -m evaluacion.armado_con_entrevista --semillas 1 2 3
"""

import argparse
import json
import tempfile
import time
from pathlib import Path

import armado
from agente import (afirmaciones_sin_respaldo, crear_agente, crear_checkpointer, llamadas_a_tools, new_thread,
                    saved_state, stream_turn)
from mcp_tienda.armado.entrevista import faltan_de_verdad, piezas_faltantes
from mcp_tienda.cliente import ClienteTienda
from mcp_tienda.config import RAIZ, ruta_catalogo_db
from model import get_model

SALIDA = RAIZ / "evaluacion" / "resultados" / "armado_con_entrevista.json"
TURNOS_MAXIMOS = 8   # entrevista (una vuelta por pregunta) + presupuesto + armado
TEMPERATURA = 0.6
MENSAJE_SIN_RESPUESTA = "No sé, elegí vos lo que más convenga."

PEDIDOS = [
    {"pedido": "Armame una PC para jugar Fortnite en 1080p. Tengo 2.800.000 y prefiero Intel.",
     "respuestas": {"uso": "Jugar", "monitor": "Un monitor común (1080p)", "transmitir": "No",
                    "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"},
     "perfil": "juegos_1080p", "presupuesto": "Gama media"},
    {"pedido": "Necesito una PC para oficina: planillas y mail. Tengo un millón.",
     "respuestas": {"uso": "Oficina o estudio", "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"},
     "perfil": "oficina", "presupuesto": "Gama baja"},
    {"pedido": "Quiero una PC para editar video en 4K, con un disco rápido y otro grande. Tengo 5.500.000.",
     "respuestas": {"uso": "Diseño o edición de video", "tipo_de_trabajo": "Edición de video",
                    "multitarea": "Sí, muchos", "archivos": "Sí, muchos", "mejora": "Sí"},
     "perfil": "edicion_video", "presupuesto": "Gama alta"},
]


def _modelo(semilla: int):
    modelo = get_model()
    campos = type(modelo).model_fields
    cambios = {k: v for k, v in {"seed": semilla, "temperature": TEMPERATURA}.items() if k in campos}
    return modelo.model_copy(update=cambios)


def _ultima_pregunta(mensajes) -> dict | None:
    """La última pregunta con botones que mostró una tool, si fue en el último turno.

    Sirve para preguntar_al_usuario (versión anterior) y para siguiente_pregunta_armado (la entrevista):
    las dos devuelven la pregunta y las opciones en el artifact.
    """
    for mensaje in reversed(mensajes):
        if mensaje.type == "tool" and isinstance(mensaje.artifact, dict) and "opciones" in mensaje.artifact:
            return {"pregunta": mensaje.artifact.get("pregunta", ""), "opciones": mensaje.artifact["opciones"]}
        if mensaje.type == "ai" and not mensaje.tool_calls:
            return None
    return None


def _respuesta_del_usuario(estado: dict, pedido: dict, ultima: dict | None) -> str | None:
    """Qué contesta el usuario simulado. None = no hay nada que contestar (la corrida puede terminar)."""
    entrevista = estado.get("entrevista") or {}
    pendiente = entrevista.get("pendiente")
    if pendiente is not None:
        return pedido["respuestas"].get(pendiente, MENSAJE_SIN_RESPUESTA)
    if not ultima:
        return None
    opciones = ultima.get("opciones", [])
    if "Armar la PC" in opciones:
        return "Armar la PC"                       # botón de la entrevista: el presupuesto ya está
    if any("cerca de" in o for o in opciones):     # pregunta de presupuesto (botones de gama)
        for opcion in opciones:
            if opcion.startswith(pedido["presupuesto"]):
                return opcion
        return MENSAJE_SIN_RESPUESTA
    return None


def _detalle_llamadas(mensajes) -> list[dict]:
    """Cada llamada a tool con sus argumentos y el comienzo de lo que devolvió (para depurar)."""
    respuestas = {m.tool_call_id: m for m in mensajes if m.type == "tool"}
    detalle = []
    for mensaje in mensajes:
        if mensaje.type != "ai":
            continue
        for llamada in mensaje.tool_calls or []:
            resp = respuestas.get(llamada["id"])
            detalle.append({"tool": llamada["name"], "argumentos": llamada["args"],
                            "respuesta": str(resp.content)[:160] if resp else None})
    return detalle


def correr(pedido: dict, semilla: int, cliente: ClienteTienda, carpeta: Path) -> dict:
    agente = crear_agente(_modelo(semilla), cliente, crear_checkpointer(carpeta / f"memoria_{semilla}.db"))
    config = new_thread()
    inicio = time.perf_counter()
    mensaje, turnos, error = pedido["pedido"], 0, None
    preguntas_de_gama = 0
    turno_fin_entrevista = None
    while turnos < TURNOS_MAXIMOS:
        turnos += 1
        try:
            for _ in stream_turn(mensaje, config, turnos, agente):
                pass
        except Exception as e:   # un turno que revienta cuenta como fallo, no corta la evaluación
            error = f"{type(e).__name__}: {e}"[:300]
            break
        estado = saved_state(config, agente)
        if turno_fin_entrevista is None and (estado.get("entrevista") or {}).get("perfil"):
            turno_fin_entrevista = turnos
        mensajes = estado.get("messages", [])
        ultima = _ultima_pregunta(mensajes)
        # Pregunta de gama o de uso por fuera de la entrevista. Las del presupuesto traen «(cerca de» en
        # sus opciones: no cuentan.
        if ultima and "gama" in ultima.get("pregunta", "").lower() \
                and not any("cerca de" in o for o in ultima.get("opciones", [])):
            preguntas_de_gama += 1
        mensaje = _respuesta_del_usuario(estado, pedido, ultima)
        if mensaje is None and mensajes and mensajes[-1].type == "ai" and "?" in str(mensajes[-1].content)[-300:]:
            mensaje = MENSAJE_SIN_RESPUESTA   # preguntó en texto, no con botones: el usuario contesta «elegí vos»
        if mensaje is None:
            break
    estado = saved_state(config, agente)
    configuracion = estado.get("configuracion") or {}
    reporte = configuracion.get("reporte") or {}
    mensajes = estado.get("messages", [])
    llamadas = llamadas_a_tools(mensajes)
    perfil = (estado.get("entrevista") or {}).get("perfil") or {}
    presupuesto = configuracion.get("presupuesto")
    componentes = configuracion.get("componentes") or {}
    faltan_perfil = [f["motivo"] for f in faltan_de_verdad(piezas_faltantes(perfil, configuracion))] if perfil else ["sin perfil"]
    cumple_perfil = bool(perfil) and bool(componentes) and not faltan_perfil
    ram_comp = componentes.get("ram")
    ram_cap = (ram_comp.get("atributos") or {}).get("capacidad_gb") if ram_comp else None
    ram_total_gb = ram_cap * armado.cantidad(configuracion, "ram") if ram_cap is not None else None
    turnos_entrevista = (turno_fin_entrevista - 1) if turno_fin_entrevista else turnos
    turnos_armado = turnos - turnos_entrevista
    return {
        "pedido": pedido["pedido"], "semilla": semilla, "turnos": turnos, "error": error,
        "turnos_entrevista": turnos_entrevista, "turnos_armado": turnos_armado,
        "entrevista_completa": bool(perfil),
        "perfil": perfil.get("clave"), "perfil_esperado": pedido["perfil"],
        "perfil_correcto": perfil.get("clave") == pedido["perfil"],
        "cumple_perfil": cumple_perfil, "faltan_perfil": faltan_perfil,
        "ram_total_gb": ram_total_gb, "tiene_gpu": "gpu" in componentes,
        "tiene_segundo_disco": "almacenamiento_extra" in componentes,
        "preguntas_de_gama": preguntas_de_gama,
        "piezas": sorted(componentes),
        "faltan": armado.faltantes(configuracion) if configuracion else ["sin armado"],
        "estado": reporte.get("estado_general", "sin_verificar"),
        "criticas_sin_datos": [r["regla"] for r in reporte.get("resultados", [])
                               if r["estado"] == "sin_datos" and r.get("critica", True)
                               and not r["detalle"].startswith("Falta elegir")],
        "se_puede_confirmar": bool(componentes) and not armado.motivos_para_no_confirmar(configuracion),
        "dentro_del_presupuesto": None if presupuesto is None else configuracion.get("total", 0) <= presupuesto,
        "total": configuracion.get("total"), "presupuesto": presupuesto,
        "llamadas": len(llamadas), "llamadas_con_error": sum(ll["error"] for ll in llamadas),
        "afirmaciones_sin_tool": len(afirmaciones_sin_respaldo(mensajes)),
        "segundos": round(time.perf_counter() - inicio, 1),
        "llamadas_detalle": _detalle_llamadas(mensajes),
        "respuesta_final": str(mensajes[-1].content)[-400:] if mensajes else "",
    }


def resumir(corridas: list[dict]) -> dict:
    n = len(corridas)
    return {
        "corridas": n,
        "entrevista_completa": sum(c["entrevista_completa"] for c in corridas),
        "perfil_correcto": sum(c["perfil_correcto"] for c in corridas),
        "preguntas_de_gama": sum(c["preguntas_de_gama"] for c in corridas),
        "completas": sum(not c["faltan"] for c in corridas),
        "cumplen_perfil": sum(bool(c.get("cumple_perfil")) for c in corridas),
        "se_pueden_confirmar": sum(c["se_puede_confirmar"] for c in corridas),
        "dentro_del_presupuesto": sum(bool(c["dentro_del_presupuesto"]) for c in corridas),
        "con_criticas_sin_datos": sum(bool(c["criticas_sin_datos"]) for c in corridas),
        "afirmaciones_sin_tool": sum(c["afirmaciones_sin_tool"] for c in corridas),
        "llamadas_promedio": round(sum(c["llamadas"] for c in corridas) / n, 1) if n else 0,
        "llamadas_con_error": sum(c["llamadas_con_error"] for c in corridas),
        "minutos_promedio": round(sum(c["segundos"] for c in corridas) / n / 60, 1) if n else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--semillas", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--pedidos", type=int, nargs="+", help="índices de PEDIDOS (por defecto, todos)")
    args = parser.parse_args()
    pedidos = [PEDIDOS[i] for i in args.pedidos] if args.pedidos else PEDIDOS

    print(f"Catálogo: {ruta_catalogo_db()}")
    corridas = []
    cliente = ClienteTienda()
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as carpeta:
            for pedido in pedidos:
                for semilla in args.semillas:
                    c = correr(pedido, semilla, cliente, Path(carpeta))
                    corridas.append(c)
                    print(f"[{semilla}] {pedido['pedido'][:40]:40} entrevista={c['entrevista_completa']} "
                          f"perfil={c['perfil']} piezas {len(c['piezas'])} faltan {c['faltan']} {c['estado']} "
                          f"confirmar={c['se_puede_confirmar']} gama-preguntada={c['preguntas_de_gama']} "
                          f"llamadas {c['llamadas']} ({c['llamadas_con_error']} con error) {c['segundos']:.0f} s"
                          + (f" ERROR {c['error']}" if c["error"] else ""), flush=True)
    finally:
        cliente.cerrar()
    resumen = resumir(corridas)
    print("\n" + json.dumps(resumen, ensure_ascii=False, indent=1))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({"catalogo": str(ruta_catalogo_db()), "resumen": resumen, "corridas": corridas},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Detalle en {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
