"""Tests del agente.

- Cableado (siempre corre): un modelo falso con respuestas fijas prueba que el agente llama a las
  tools del servidor MCP y que la evaluación mide lo que tiene que medir.
- Smoke con Ollama (marcado `ollama`): el LLM local resuelve un pedido simple. Se saltea si no
  hay un servidor Ollama con el modelo configurado.
"""

import json
import os
import urllib.request

import pytest
from langchain_core.messages import AIMessage

from agente import crear_agente
from evaluacion.agente_simple import evaluar_pedido
from tests.falsos import ModeloFalso
from tests.falsos import llamada as _llamada


def test_agente_llama_a_buscar_y_responde(catalogo, cliente):
    modelo = ModeloFalso(messages=iter([
        _llamada("buscar_productos", {"categoria": "cables", "atributos": {"conector_a": "HDMI", "largo_m": 2}}),
        AIMessage(content="Te recomiendo el CAB002 (Cable Ugreen HDMI 2 m), $18.500, stock 13."),
    ]))
    r = evaluar_pedido(crear_agente(modelo=modelo, cliente=cliente), catalogo,
                       {"pedido": "Necesito un cable HDMI de 2 metros", "codigos_validos": ["CAB002"]})
    assert r["exito"] and r["llamadas"] == 1 and r["llamadas_con_error"] == 0


def test_evaluacion_detecta_codigo_inventado_y_llamada_con_error(catalogo, cliente):
    modelo = ModeloFalso(messages=iter([
        _llamada("buscar_productos", {"categoria": "cables", "atributos": {"color": "rojo"}}),
        AIMessage(content="Te recomiendo el CAB999 y el CAB002."),
    ]))
    r = evaluar_pedido(crear_agente(modelo=modelo, cliente=cliente), catalogo,
                       {"pedido": "cable rojo", "codigos_validos": ["CAB002"]})
    assert not r["exito"]
    assert r["codigos_inventados"] == ["CAB999"]
    assert r["llamadas_con_error"] == 1


def _ollama_disponible() -> bool:
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    modelo = os.getenv("MODEL_NAME", "qwen3:4b")
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=2) as respuesta:
            modelos = [m["name"] for m in json.load(respuesta)["models"]]
    except OSError:
        return False
    return any(m == modelo or m.startswith(f"{modelo}:") for m in modelos)


@pytest.mark.ollama
@pytest.mark.skipif(not _ollama_disponible(), reason="No hay Ollama con el modelo configurado")
def test_smoke_llm_local_resuelve_pedido_simple(catalogo, cliente):
    r = evaluar_pedido(crear_agente(cliente=cliente), catalogo,
                       {"pedido": "Necesito un cable HDMI de 2 metros", "codigos_validos": ["CAB002"]})
    assert r["llamadas"] >= 1, "el modelo respondió sin buscar en el catálogo"
    assert not r["codigos_inventados"], r["respuesta"]
    assert r["exito"], r["respuesta"]
