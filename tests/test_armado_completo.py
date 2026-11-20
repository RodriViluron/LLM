"""Paso 13 (#26, parte 2): armado completo controlado por código después de la entrevista.

Prueba con modelo falso y el servidor MCP real sobre el catálogo de prueba:
- `piezas_faltantes` controla CPU, cooler, motherboard, RAM (capacidad total), ambos discos, GPU y fuente;
- RAM automática en `agregar_o_reemplazar_componente` (cantidad=2 para 32 GB con módulo de 16 GB, error si no entra en 2);
- `estado_perfil` («Faltan: …» / «Armado completo según el perfil.») en el texto de las tools, nunca en `artifact`;
- middleware `armado_completo`: reintenta 1 vez si pregunta marca («¿Intel o AMD?») o cierra con faltantes,
  menciona preferencia previa si hubo, deja pasar un segundo fallo, y nunca bloquea preguntas de presupuesto
  ni casos donde el presupuesto no alcanza.
"""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import agente as modulo_agente
import armado
from agente import PROMPT_SISTEMA, crear_agente
from mcp_tienda.armado.entrevista import piezas_faltantes, siguiente, texto_piezas_faltantes
from tests.conftest import TABLA_GAMAS
from tests.falsos import ModeloFalso, buscar, llamada, modelo_con, texto
from tools import BASE_DIR, Context

PERFIL_OFICINA = siguiente({
    "uso": "Oficina o estudio", "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No",
})["perfil"]

PERFIL_EDICION = siguiente({
    "uso": "Diseño o edición de video", "tipo_de_trabajo": "Edición de video",
    "multitarea": "Sí, muchos", "archivos": "Sí, muchos", "mejora": "Sí",
})["perfil"]

ARMADO_OFICINA = {
    "cpu": "CPU003",          # Ryzen 5 5600G con video integrado y cooler
    "motherboard": "MOT003",
    "ram": "RAM001",          # 8 GB
    "almacenamiento": "ALM003",
    "fuente": "FUE006",
    "gabinete": "GAB004",
}

ARMADO_EDICION = {
    "cpu": "CPU006",          # Ryzen 5 7600 (AM5, trae cooler)
    "motherboard": "MOT007",
    "ram": "RAM008",          # 16 GB DDR5 (con cantidad=2 son 32 GB)
    "gpu": "GPU003",
    "almacenamiento": "ALM003",
    "almacenamiento_extra": "ALM001",
    "fuente": "FUE006",
    "gabinete": "GAB004",
}


class ModeloQueAnota(ModeloFalso):
    """Modelo falso que guarda los mensajes recibidos en cada llamada real."""
    recibidos: list = []

    def _generate(self, messages, *args, **kwargs):
        self.recibidos.append(list(messages))
        return super()._generate(messages, *args, **kwargs)

    def _stream(self, messages, *args, **kwargs):
        self.recibidos.append(list(messages))
        yield from super()._stream(messages, *args, **kwargs)


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo_agente, "CONV_FILE", tmp_path / "conversaciones.txt")


def _config_con(cliente, piezas: dict, cantidades: dict | None = None, presupuesto: float = 5_000_000) -> dict:
    config = armado.nueva(presupuesto=presupuesto, perfil_uso="prueba")
    for lugar, codigo in piezas.items():
        cant = (cantidades or {}).get(lugar, 1)
        config = armado.poner_componente(config, lugar, codigo, cliente, cantidad=cant)
    return config


# --- piezas_faltantes (determinista, sin LLM) -----------------------------------

def test_piezas_faltantes_detecta_gpu_y_segundo_disco_del_perfil(cliente):
    sin_gpu_ni_extra = _config_con(cliente, {
        k: v for k, v in ARMADO_EDICION.items() if k not in ("gpu", "almacenamiento_extra")
    }, cantidades={"ram": 2})
    faltan = piezas_faltantes(PERFIL_EDICION, sin_gpu_ni_extra)
    assert [f["lugar"] for f in faltan] == ["almacenamiento_extra", "gpu"]
    resumen = texto_piezas_faltantes(faltan)
    assert resumen.startswith("Faltan: ") and "segundo disco" in resumen and "GPU dedicada" in resumen


def test_piezas_faltantes_detecta_ram_insuficiente_y_cpu_sin_integrado(cliente):
    solo_16 = _config_con(cliente, ARMADO_EDICION, cantidades={"ram": 1})
    faltan = piezas_faltantes(PERFIL_EDICION, solo_16)
    assert [f["lugar"] for f in faltan] == ["ram"]
    assert "16 GB" in faltan[0]["motivo"] and "32 GB" in faltan[0]["motivo"]

    # Oficina (gpu=False) con CPU sin video integrado (CPU001) exige GPU dedicada.
    oficina_sin_igpu = _config_con(cliente, {**ARMADO_OFICINA, "cpu": "CPU001"})
    assert [f["lugar"] for f in piezas_faltantes(PERFIL_OFICINA, oficina_sin_igpu)] == ["gpu"]

    # Oficina con CPU003 (con video integrado) queda completo sin GPU.
    oficina_ok = _config_con(cliente, ARMADO_OFICINA)
    assert piezas_faltantes(PERFIL_OFICINA, oficina_ok) == []
    assert texto_piezas_faltantes([]) == "Armado completo según el perfil."


def test_piezas_faltantes_no_asume_si_falta_dato_de_video_integrado():
    config_sin_dato = {
        "componentes": {
            "cpu": {"atributos": {}},
            "motherboard": {"atributos": {}},
            "ram": {"atributos": {"capacidad_gb": 8}},
            "almacenamiento": {"atributos": {}},
            "gabinete": {"atributos": {"incluye_fuente": "si"}},
        },
        "cantidades": {},
    }
    faltan = piezas_faltantes(PERFIL_OFICINA, config_sin_dato)
    assert [f["lugar"] for f in faltan] == ["gpu"]
    assert "sin datos" in faltan[0]["motivo"]


# --- RAM automática y estado_perfil en tools ------------------------------------

def test_ram_automatica_pone_cantidad_2_y_rechaza_modulo_chico(cliente):
    entrevista = {"respuestas": {}, "pendiente": None, "perfil": PERFIL_EDICION, "presupuesto": 5_500_000}

    # RAM003 es de 16 GB y el perfil de Edición pide 32 GB -> cantidad=2 automática aunque no la pase.
    modelo_ok = modelo_con(
        buscar("ram"),
        llamada("agregar_o_reemplazar_componente", {"lugar": "ram", "codigo": "RAM003"}, "a1"),
        texto("ok"), texto("ok"),
    )
    res_ok = crear_agente(modelo_ok, cliente).invoke(
        {"messages": [("user", "agregá RAM")], "entrevista": entrevista},
        context=Context(turn=1),
    )
    assert res_ok["configuracion"]["cantidades"]["ram"] == 2
    assert res_ok["configuracion"]["componentes"]["ram"]["codigo"] == "RAM003"
    tool_add = next(m for m in res_ok["messages"]
                    if isinstance(m, ToolMessage) and m.name == "agregar_o_reemplazar_componente")
    datos_add = json.loads(tool_add.content)
    assert datos_add["estado_perfil"].startswith("Faltan: ")
    assert set(tool_add.artifact) == {"configuracion"}   # estado_perfil NO va al artifact

    # RAM001 es de 8 GB -> necesita 4 módulos (>2): error claro sin agregarla.
    modelo_err = modelo_con(
        buscar("ram"),
        llamada("agregar_o_reemplazar_componente", {"lugar": "ram", "codigo": "RAM001"}, "a2"),
        texto("ok"),
    )
    res_err = crear_agente(modelo_err, cliente).invoke(
        {"messages": [("user", "agregá RAM")], "entrevista": entrevista},
        context=Context(turn=1),
    )
    assert not res_err.get("configuracion")
    msg_err = next(m for m in res_err["messages"]
                   if isinstance(m, ToolMessage) and m.name == "agregar_o_reemplazar_componente")
    assert "módulo más grande" in json.loads(msg_err.content)["error"]


def test_obtener_configuracion_informa_armado_completo_en_texto_y_no_en_artifact(cliente):
    completa = _config_con(cliente, ARMADO_OFICINA, presupuesto=1_000_000)
    entrevista = {"respuestas": {}, "pendiente": None, "perfil": PERFIL_OFICINA, "presupuesto": 1_000_000}
    agente = crear_agente(modelo_con(llamada("obtener_configuracion", {}, "o1"), texto("Listo")), cliente)
    res = agente.invoke(
        {"messages": [("user", "mostrá cómo quedó")], "entrevista": entrevista, "configuracion": completa},
        context=Context(turn=1),
    )
    msg = next(m for m in res["messages"] if isinstance(m, ToolMessage) and m.name == "obtener_configuracion")
    assert json.loads(msg.content)["estado_perfil"] == "Armado completo según el perfil."
    assert set(msg.artifact) == {"configuracion"}


# --- Middleware armado_completo -------------------------------------------------

def test_pregunta_marca_con_faltantes_reintenta_una_vez_y_recuerda_preferencia(cliente):
    entrevista = {"respuestas": {}, "pendiente": None, "perfil": PERFIL_OFICINA, "presupuesto": 1_000_000}
    modelo = ModeloQueAnota(messages=iter([
        llamada("preguntar_al_usuario", {"pregunta": "¿Prefieres Intel o AMD?", "opciones": ["Intel", "AMD"]}, "p1"),
        llamada("buscar_pieza_armado", {"lugar": "cpu"}, "b1"),
        texto("Todavía no elegí las piezas."),
        texto("Todavía faltan piezas, podés pedirlas."),   # segundo fallo en texto: pasa sin bucle
    ]))
    agente = crear_agente(modelo, cliente)
    res = agente.invoke({
        "messages": [("user", "Armame una PC de oficina, prefiero Intel")],
        "entrevista": entrevista,
        "configuracion": armado.nueva(1_000_000, "Oficina y estudio"),
    }, context=Context(turn=1))

    assert len(modelo.recibidos) == 4
    aviso_marca = modelo.recibidos[1][-1].text
    assert "[Aviso del sistema]" in aviso_marca and "Faltan:" in aviso_marca
    assert "Intel" in aviso_marca and "No le preguntes la marca" in aviso_marca
    assert not any(isinstance(m, ToolMessage) and m.name == "preguntar_al_usuario" for m in res["messages"])


def test_texto_final_con_faltantes_reintenta_una_vez_y_el_segundo_fallo_pasa(cliente):
    entrevista = {"respuestas": {}, "pendiente": None, "perfil": PERFIL_OFICINA, "presupuesto": 1_000_000}
    parcial = _config_con(cliente, {"cpu": "CPU003"}, presupuesto=1_000_000)
    modelo = ModeloQueAnota(messages=iter([
        texto("Avisame cómo seguimos con la PC."),
        texto("Perdón, elegí vos el resto más adelante."),
    ]))
    agente = crear_agente(modelo, cliente)
    res = agente.invoke({
        "messages": [("user", "seguí armando")],
        "entrevista": entrevista,
        "configuracion": parcial,
    }, context=Context(turn=1))

    assert len(modelo.recibidos) == 2
    aviso = modelo.recibidos[1][-1].text
    assert "Faltan:" in aviso and "motherboard" in aviso and "No le preguntes la marca" in aviso
    assert res["messages"][-1].text == "Perdón, elegí vos el resto más adelante."


def test_pregunta_del_presupuesto_y_presupuesto_insuficiente_no_se_bloquean(cliente):
    # Pregunta del presupuesto (aunque haya configuracion iniciada y faltantes): no se bloquea.
    entrevista_sin_pres = {"respuestas": {}, "pendiente": None, "perfil": PERFIL_OFICINA}
    modelo_pres = ModeloQueAnota(messages=iter([
        llamada("preguntar_al_usuario", {
            "pregunta": "¿Cuál es tu presupuesto?",
            "opciones": ["Gama baja (cerca de $ 1.000.000)", "Otro monto"],
        }, "p_pres"),
    ]))
    res_pres = crear_agente(modelo_pres, cliente).invoke({
        "messages": [("user", "seguimos")],
        "entrevista": entrevista_sin_pres,
        "configuracion": armado.nueva(None, "Oficina y estudio"),
    }, context=Context(turn=1))
    assert len(modelo_pres.recibidos) == 1
    assert next(m for m in res_pres["messages"] if isinstance(m, ToolMessage) and m.name == "preguntar_al_usuario")

    # Presupuesto insuficiente: no bloquea la respuesta explicando que no alcanza.
    modelo_insuf = ModeloQueAnota(messages=iter([
        texto("Con $ 200.000 no alcanza para una PC completa: ¿querés subir el presupuesto?"),
    ]))
    res_insuf = crear_agente(modelo_insuf, cliente).invoke({
        "messages": [("user", "tengo 200.000")],
        "entrevista": {**entrevista_sin_pres, "presupuesto": 200_000},
        "configuracion": armado.nueva(200_000, "Oficina y estudio"),
    }, context=Context(turn=1))
    assert len(modelo_insuf.recibidos) == 1
    assert "no alcanza" in res_insuf["messages"][-1].text


def test_prompt_y_skill_indican_no_preguntar_marca():
    assert "Con el perfil completo no preguntes la marca" in PROMPT_SISTEMA
    skill = (BASE_DIR / "skills" / "armado_pc.md").read_text(encoding="utf-8")
    assert "Con el perfil completo no preguntes la marca" in skill and "Cambiar" in skill


# --- Paso 13, Fortnite: socket en el texto y «sin datos» de video ----------------------

@pytest.mark.parametrize("texto_modelo, limpio", [
    ("LGA1700", None), ("B760 LGA 1700", "B760"), ("socket AM5", None), ("B550 AM4", "B550"),
    ("placa 1700 ddr5", "placa ddr5"), ("ASUS", "ASUS"), ("17000", "17000"), (None, None),
])
def test_el_socket_no_va_en_el_texto_de_busqueda(texto_modelo, limpio):
    from tools import sin_socket
    assert sin_socket(texto_modelo) == limpio


def test_sin_datos_de_video_se_avisa_pero_no_es_una_pieza_faltante():
    from mcp_tienda.armado.entrevista import faltan_de_verdad
    config_sin_dato = {
        "componentes": {
            "cpu": {"atributos": {}},
            "motherboard": {"atributos": {}},
            "ram": {"atributos": {"capacidad_gb": 8}},
            "almacenamiento": {"atributos": {}},
            "gabinete": {"atributos": {"incluye_fuente": "si"}},
        },
        "cantidades": {},
    }
    faltan = piezas_faltantes(PERFIL_OFICINA, config_sin_dato)
    assert faltan_de_verdad(faltan) == []
    texto_estado = texto_piezas_faltantes(faltan)
    assert texto_estado.startswith("Armado completo según el perfil.") and "Aviso: sin datos" in texto_estado
