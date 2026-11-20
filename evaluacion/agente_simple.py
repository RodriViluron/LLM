"""Evaluación del agente sobre pedidos simples (Fase 0).

Métricas por pedido y en total:
- éxito: la respuesta final menciona un código válido y ningún código inexistente,
- llamadas a tools, y cuántas dieron error (llamada mal formada o rechazada por la tool),
- códigos inventados (mencionados en la respuesta pero que no existen en el catálogo).

Es el germen de la métrica «Agente» de CLAUDE.md: en la Fase 4 se corre igual con el modelo
base y con el afinado.

Uso:  python -m evaluacion.agente_simple       (necesita el modelo local del .env)
"""

import json
import os
import re
import time

import yaml
from langchain_core.messages import HumanMessage

from agente import crear_agente, llamadas_a_tools
from mcp_tienda.catalogo import Catalogo
from mcp_tienda.config import RAIZ
from tools import Context

PATRON_CODIGO = re.compile(r"\b[A-Z]{3}\d{3}\b")


def evaluar_pedido(agente, catalogo: Catalogo, pedido: dict) -> dict:
    inicio = time.perf_counter()
    # Cada pedido es una conversación nueva de un solo turno (el agente se crea sin memoria).
    resultado = agente.invoke({"messages": [HumanMessage(pedido["pedido"])]}, context=Context(turn=1))
    mensajes = resultado["messages"]
    respuesta = str(mensajes[-1].content)
    mencionados = set(PATRON_CODIGO.findall(respuesta))
    inventados = sorted(c for c in mencionados if catalogo.obtener(c) is None)
    validos = sorted(mencionados & set(pedido["codigos_validos"]))
    llamadas = llamadas_a_tools(mensajes)
    return {
        "pedido": pedido["pedido"],
        "exito": bool(validos) and not inventados,
        "codigos_validos_mencionados": validos,
        "codigos_inventados": inventados,
        "llamadas": len(llamadas),
        "llamadas_con_error": sum(ll["error"] for ll in llamadas),
        "detalle_llamadas": [{"tool": ll["tool"], "argumentos": ll["argumentos"], "error": ll["error"]}
                             for ll in llamadas],
        "segundos": round(time.perf_counter() - inicio, 1),
        "respuesta": respuesta,
    }


def evaluar(agente, catalogo: Catalogo, pedidos: list[dict]) -> dict:
    resultados = [evaluar_pedido(agente, catalogo, p) for p in pedidos]
    n = len(resultados)
    total_llamadas = sum(r["llamadas"] for r in resultados)
    return {
        "pedidos": n,
        "tasa_exito": sum(r["exito"] for r in resultados) / n,
        "llamadas_promedio": total_llamadas / n,
        "tasa_llamadas_con_error": (sum(r["llamadas_con_error"] for r in resultados) / total_llamadas
                                    if total_llamadas else 0.0),
        "codigos_inventados": sum(len(r["codigos_inventados"]) for r in resultados),
        "resultados": resultados,
    }


def cargar_pedidos() -> list[dict]:
    ruta = RAIZ / "evaluacion" / "conjuntos" / "pedidos_simples.yaml"
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def main() -> None:
    catalogo = Catalogo()
    r = evaluar(crear_agente(), catalogo, cargar_pedidos())
    modelo = os.getenv("MODEL_NAME", "qwen3:4b")
    for x in r["resultados"]:
        marca = "OK " if x["exito"] else "MAL"
        print(f"[{marca}] {x['pedido']}  ({x['llamadas']} llamadas, {x['llamadas_con_error']} con error, "
              f"{x['segundos']} s)")
    print(f"\nModelo: {modelo}")
    print(f"Éxito: {r['tasa_exito']:.0%}   Llamadas promedio: {r['llamadas_promedio']:.1f}   "
          f"Llamadas con error: {r['tasa_llamadas_con_error']:.0%}   Códigos inventados: {r['codigos_inventados']}")
    salida = RAIZ / "evaluacion" / "resultados"
    salida.mkdir(exist_ok=True)
    archivo = salida / f"agente_simple_{modelo.replace(':', '_').replace('/', '_')}.json"
    archivo.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Detalle en {archivo}")


if __name__ == "__main__":
    main()
