"""Métricas de afirmaciones sin respaldo: acciones sin tool (problema 20) y montos inventados (problema 2).

Recorre las conversaciones guardadas (memoria.db) y cuenta:
- los turnos cuya respuesta final dice «agregué…», «cambié…», «buscando…» sin ninguna tool en ese turno
  que lo respalde (ver agente.accion_sin_respaldo);
- los montos en pesos que el agente mostró (en el texto o en los botones) y que no salieron de una tool,
  del usuario ni de la escala del reparto del presupuesto (ver agente.montos_sin_respaldo).

Sirve para comparar antes y después de un cambio y, en la Fase 4, el modelo base contra el afinado.

Uso:  python -m evaluacion.afirmaciones_sin_tool [--memoria ruta/a/memoria.db]
"""

import argparse
import json
from pathlib import Path

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agente import (
    CONV_FILE,
    MEMORIA_DB,
    _config,
    afirmaciones_sin_respaldo,
    crear_agente,
    crear_checkpointer,
    escala_de_presupuesto,
    montos_sin_respaldo,
)
from mcp_tienda.config import RAIZ


def evaluar(memoria: Path) -> dict:
    # El modelo no se usa: el agente solo sirve para leer el estado guardado.
    agente = crear_agente(modelo=FakeListChatModel(responses=["-"]), checkpointer=crear_checkpointer(memoria))
    escala = escala_de_presupuesto()
    filas, montos, turnos = [], [], 0
    for thread_id in CONV_FILE.read_text().split() if CONV_FILE.exists() else []:
        mensajes = agente.get_state(_config(thread_id)).values.get("messages", [])
        turnos += sum(m.type == "human" for m in mensajes)
        filas += [{"conversacion": thread_id, **f} for f in afirmaciones_sin_respaldo(mensajes)]
        montos += [{"conversacion": thread_id, **f} for f in montos_sin_respaldo(mensajes, escala)]
    return {"turnos": turnos, "afirmaciones_sin_tool": len(filas),
            "tasa": round(len(filas) / turnos, 3) if turnos else 0.0, "detalle": filas,
            "montos_sin_respaldo": len(montos), "detalle_montos": montos}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--memoria", type=Path, default=MEMORIA_DB)
    resultado = evaluar(parser.parse_args().memoria)
    for f in resultado["detalle"]:
        print(f"{f['conversacion'][:8]} turno {f['turno']:2} [{f['tipo']}] {f['respuesta'][:100]!r}")
    for f in resultado["detalle_montos"]:
        print(f"{f['conversacion'][:8]} monto sin respaldo {f['monto']!r} en {f['texto'][:80]!r}")
    print(f"\n{resultado['afirmaciones_sin_tool']} afirmaciones sin tool en {resultado['turnos']} turnos "
          f"(tasa {resultado['tasa']:.1%}); {resultado['montos_sin_respaldo']} montos sin respaldo")
    salida = RAIZ / "evaluacion" / "resultados" / "afirmaciones_sin_tool.json"
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Detalle en {salida}")


if __name__ == "__main__":
    main()
