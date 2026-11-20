"""Prueba de punta a punta del armado con el modelo local (paso 9 de PROBLEMAS_DETECTADOS.md).

Le pide al agente que arme una PC completa y mide cómo quedó, con las mismas funciones que usa la
interfaz (armado.motivos_para_no_confirmar). Por cada pedido y semilla:

- piezas puestas y lugares obligatorios que faltan;
- estado de compatibilidad y reglas críticas en «sin datos» (sin contar «Falta elegir»);
- si el usuario podría confirmar el pedido y si entra en el presupuesto;
- llamadas a tools, llamadas con error, afirmaciones de acción sin tool y segundos.

La conversación tiene hasta TURNOS_MAXIMOS turnos: si el agente pregunta (preguntar_al_usuario o
una respuesta que termina en «?»), se le contesta RESPUESTA_FIJA, como un usuario que delega.

Semillas: con temperatura 0 todas las semillas dan lo mismo, así que se usa la temperatura que
recomienda Qwen3 (0,6) con una semilla fija por corrida. Una diferencia menor que la variación
entre semillas no cuenta como mejora.

Uso (el catálogo se elige con AMN_CATALOGO_DB, por ejemplo el real):
    uv run python -m evaluacion.armado_punta_a_punta --semillas 1 2 3
"""

import argparse
import json
import tempfile
import time
from pathlib import Path

import armado
from agente import (afirmaciones_sin_respaldo, crear_agente, crear_checkpointer, llamadas_a_tools, new_thread,
                    saved_state, stream_turn)
from mcp_tienda.cliente import ClienteTienda
from mcp_tienda.config import RAIZ, ruta_catalogo_db
from model import get_model

SALIDA = RAIZ / "evaluacion" / "resultados" / "armado_punta_a_punta.json"
TURNOS_MAXIMOS = 4
TEMPERATURA = 0.6
RESPUESTA_FIJA = "Elegí vos lo que más convenga y seguí armando la PC completa, sin preguntarme más."

PEDIDOS = [
    "Armame una PC para jugar Fortnite en 1080p. Tengo $2.800.000 y prefiero Intel.",
    "Necesito una PC para oficina: planillas, mails y navegar. Tengo $1.000.000.",
    "Quiero una PC para editar video en 4K con dos discos: uno rápido para el sistema y uno grande para "
    "guardar. Tengo $5.500.000.",
]


def _modelo(semilla: int):
    modelo = get_model()
    campos = type(modelo).model_fields
    cambios = {k: v for k, v in {"seed": semilla, "temperature": TEMPERATURA}.items() if k in campos}
    return modelo.model_copy(update=cambios)


def _termina_en_pregunta(estado: dict) -> bool:
    ultimo = estado["messages"][-1]
    if ultimo.type == "tool" and ultimo.name == "preguntar_al_usuario":
        return True
    return ultimo.type == "ai" and "?" in str(ultimo.content)[-300:]


def correr(pedido: str, semilla: int, cliente: ClienteTienda, carpeta: Path) -> dict:
    agente = crear_agente(_modelo(semilla), cliente, crear_checkpointer(carpeta / f"memoria_{semilla}.db"))
    config = new_thread()
    inicio = time.perf_counter()
    mensaje, turnos, error = pedido, 0, None
    while turnos < TURNOS_MAXIMOS:
        turnos += 1
        try:
            for _ in stream_turn(mensaje, config, turnos, agente):
                pass
        except Exception as e:   # un turno que revienta cuenta como fallo, no corta la evaluación
            error = f"{type(e).__name__}: {e}"[:300]
            break
        estado = saved_state(config, agente)
        configuracion = estado.get("configuracion") or {}
        if not armado.faltantes(configuracion) and configuracion.get("componentes"):
            break
        if not _termina_en_pregunta(estado):
            break
        mensaje = RESPUESTA_FIJA
    estado = saved_state(config, agente)
    configuracion = estado.get("configuracion") or {}
    reporte = configuracion.get("reporte") or {}
    mensajes = estado.get("messages", [])
    llamadas = llamadas_a_tools(mensajes)
    criticas_sin_datos = [r["regla"] for r in reporte.get("resultados", [])
                          if r["estado"] == "sin_datos" and r.get("critica", True)
                          and not r["detalle"].startswith("Falta elegir")]
    presupuesto = configuracion.get("presupuesto")
    return {
        "pedido": pedido, "semilla": semilla, "turnos": turnos, "error": error,
        "piezas": sorted(configuracion.get("componentes", {})),
        "cantidades": configuracion.get("cantidades") or {},
        "faltan": armado.faltantes(configuracion) if configuracion else ["sin armado"],
        "estado": reporte.get("estado_general", "sin_verificar"),
        "no_cumple": [r["detalle"] for r in reporte.get("resultados", []) if r["estado"] == "no_cumple"],
        "criticas_sin_datos": criticas_sin_datos,
        "se_puede_confirmar": bool(configuracion.get("componentes")) and not armado.motivos_para_no_confirmar(configuracion),
        "dentro_del_presupuesto": None if presupuesto is None else configuracion.get("total", 0) <= presupuesto,
        "total": configuracion.get("total"), "presupuesto": presupuesto,
        "llamadas": len(llamadas), "llamadas_con_error": sum(ll["error"] for ll in llamadas),
        "afirmaciones_sin_tool": len(afirmaciones_sin_respaldo(mensajes)),
        "segundos": round(time.perf_counter() - inicio, 1),
        "respuesta_final": str(mensajes[-1].content)[-400:] if mensajes else "",
    }


def resumir(corridas: list[dict]) -> dict:
    n = len(corridas)
    return {
        "corridas": n,
        "completas": sum(not c["faltan"] for c in corridas),
        "compatibles": sum(c["estado"] == "compatible" for c in corridas),
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
                    print(f"[{semilla}] {pedido[:45]:45} piezas {len(c['piezas'])} faltan {c['faltan']} "
                          f"{c['estado']} confirmar={c['se_puede_confirmar']} presupuesto={c['dentro_del_presupuesto']} "
                          f"críticas sin datos={c['criticas_sin_datos']} llamadas {c['llamadas']} "
                          f"({c['llamadas_con_error']} con error) {c['segundos']:.0f} s"
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
