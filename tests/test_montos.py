"""Problema 2: el agente inventaba montos al pedir el presupuesto («5000 / 8000 / 10000»).

- La escala de referencia (total típico por gama) sale de rag/docs/reparto_presupuesto.md.
- El detector marca montos que no salieron de una tool ni de esa escala, también en los botones.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agente import escala_de_presupuesto, montos_sin_respaldo

REPARTO = """\
# Reparto del presupuesto por componente

> **Fecha:** 2026-11-18

## Reparto del presupuesto en gama baja

Gama baja: algo. Una PC de gama baja en la tienda cuesta típicamente $ 998.000 (entre $ 919.000 y $ 1.119.000).

## Reparto del presupuesto en gama media

Gama media: algo. Una PC de gama media en la tienda cuesta típicamente $ 2.762.000 (entre $ 2.488.000 y $ 3.035.000).
"""


def _doc(tmp_path, texto=REPARTO):
    ruta = tmp_path / "reparto_presupuesto.md"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_la_escala_sale_del_reparto(tmp_path):
    escala = escala_de_presupuesto(_doc(tmp_path))
    assert escala["fecha"] == "2026-11-18"
    assert [g["gama"] for g in escala["gamas"]] == ["baja", "media"]
    baja, media = escala["gamas"]
    assert (baja["tipico"], baja["desde"], baja["hasta"]) == (998_000, 919_000, 1_119_000)
    assert baja["opcion"] == "Gama baja (cerca de $ 1.000.000)"
    assert media["opcion"] == "Gama media (cerca de $ 2.800.000)"


def test_sin_documento_la_escala_queda_vacia(tmp_path):
    assert escala_de_presupuesto(tmp_path / "no_existe.md") == {"fecha": None, "gamas": []}


def test_el_prompt_trae_la_escala_del_reparto(tmp_path, monkeypatch):
    import agente

    monkeypatch.setattr(agente, "REPARTO_DOC", _doc(tmp_path))
    prompt = agente.construir_prompt()
    assert "Presupuesto de referencia" in prompt and "(reparto_presupuesto.md, 2026-11-18)" in prompt
    assert "- Gama media (cerca de $ 2.800.000): entre $ 2.488.000 y $ 3.035.000" in prompt
    assert "para preguntar el presupuesto de una PC usá preguntar_al_usuario" in prompt
    # si cambia el reparto, cambia el prompt
    _doc(tmp_path, REPARTO.replace("2.762.000", "3.150.000"))
    assert "Gama media (cerca de $ 3.200.000)" in agente.construir_prompt()
    # sin documento, el prompt no se rompe y no da montos
    monkeypatch.setattr(agente, "REPARTO_DOC", tmp_path / "no_existe.md")
    assert "Preguntá el monto sin dar ejemplos" in agente.construir_prompt()


def _pregunta(pregunta, opciones):
    return AIMessage(content="", tool_calls=[{"name": "preguntar_al_usuario", "id": "p",
                                              "args": {"pregunta": pregunta, "opciones": opciones}}])


def test_detecta_montos_inventados_en_los_botones_aunque_no_lleven_signo(tmp_path):
    escala = escala_de_presupuesto(_doc(tmp_path))
    casos = [
        _pregunta("¿Cuánto tenés de presupuesto?", ["5000", "7000", "10000", "15000"]),
        _pregunta("¿Cuál es tu presupuesto?", ["Menos de $500", "$500-$1000", "Más de $2000"]),
        _pregunta("¿Cuánto querés gastar?", ["20.000", "35.000", "50.000"]),
    ]
    for mensaje in casos:
        assert montos_sin_respaldo([HumanMessage("Quiero una PC"), mensaje], escala), mensaje.tool_calls
    # preguntar_al_usuario repite la pregunta en su resultado: eso no respalda los montos que inventó
    pregunta = _pregunta("¿Cuánto querés gastar? (Ej: 20.000, 35.000)", ["20.000", "35.000"])
    eco = ToolMessage("¿Cuánto querés gastar? (Ej: 20.000, 35.000)", tool_call_id="p", name="preguntar_al_usuario")
    assert montos_sin_respaldo([HumanMessage("Quiero una PC"), pregunta, eco], escala)


def test_no_marca_montos_de_la_escala_ni_de_las_tools(tmp_path):
    escala = escala_de_presupuesto(_doc(tmp_path))
    mensajes = [
        HumanMessage("Quiero una PC"),
        _pregunta("¿Qué presupuesto tenés?", [g["opcion"] for g in escala["gamas"]] + ["Otro monto"]),
        HumanMessage("Gama media"),
        ToolMessage('{"productos": [{"codigo": "12400F", "precio": 374950.0}]}', tool_call_id="b",
                    name="buscar_productos"),
        AIMessage(content="Te recomiendo el 12400F a $ 374.950. Una PC de gama media cuesta cerca de $ 2.762.000."),
    ]
    assert montos_sin_respaldo(mensajes, escala) == []


def test_no_confunde_otros_numeros_con_montos(tmp_path):
    escala = escala_de_presupuesto(_doc(tmp_path))
    texto = AIMessage(content="Para 1080p alcanza con una RTX 5060, 16 GB de RAM, una fuente de 650 W y el i5-12400F.")
    assert montos_sin_respaldo([HumanMessage("x"), texto], escala) == []
    # el monto que escribe el usuario cuenta como respaldo
    eco = AIMessage(content="Perfecto, con $ 1.500.000 armamos algo de gama media.")
    assert montos_sin_respaldo([HumanMessage("Tengo 1.500.000"), eco], escala) == []
