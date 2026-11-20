"""Entrevista del armado por código (paso 10, problema 26).

El código decide qué pregunta sigue y qué perfil sale de las respuestas; el modelo solo elige una
opción de la lista que devuelve la tool. Acá se prueban los caminos del árbol y los filtros que
salen del perfil.
"""

import pytest

from mcp_tienda.armado.entrevista import ErrorEntrevista, cantidad_de_ram, filtros_del_perfil, siguiente

OFICINA = "Oficina o estudio"
JUGAR = "Jugar"


def pregunta_de(resultado: dict) -> str:
    assert not resultado["completa"], resultado
    return resultado["pregunta"]["id"]


def test_la_primera_pregunta_es_el_uso_con_sus_opciones():
    r = siguiente({})
    assert r["completa"] is False and pregunta_de(r) == "uso"
    assert r["pregunta"]["opciones"] == ["Oficina o estudio", "Jugar", "Diseño o edición de video", "Programar"]


def test_oficina_pregunta_multitarea_archivos_y_mejora_y_termina():
    r = siguiente({"uso": OFICINA})
    assert pregunta_de(r) == "multitarea"                 # no pregunta monitor ni tipo de trabajo
    r = siguiente({"uso": OFICINA, "multitarea": "Lo normal"})
    assert pregunta_de(r) == "archivos"
    r = siguiente({"uso": OFICINA, "multitarea": "Lo normal", "archivos": "No tanto"})
    assert pregunta_de(r) == "mejora"
    r = siguiente({"uso": OFICINA, "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})
    assert r["completa"] is True
    perfil = r["perfil"]
    assert perfil["clave"] == "oficina" and perfil["gama"] == "baja"
    assert perfil["ram_gb"] == 8 and perfil["gpu"] is False and perfil["segundo_disco"] is False
    assert perfil["placa_escalable"] is False


def test_jugar_pregunta_la_pantalla_y_en_1440p_pregunta_transmitir():
    r = siguiente({"uso": JUGAR})
    assert pregunta_de(r) == "monitor"
    r = siguiente({"uso": JUGAR, "monitor": "Un monitor 2K (1440p)"})
    assert pregunta_de(r) == "transmitir"
    r = siguiente({"uso": JUGAR, "monitor": "Un monitor 2K (1440p)", "transmitir": "No"})
    assert pregunta_de(r) == "multitarea"
    final = siguiente({"uso": JUGAR, "monitor": "Un monitor 2K (1440p)", "transmitir": "No",
                       "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})
    assert final["perfil"]["clave"] == "juegos_1440p" and final["perfil"]["gama"] == "alta"


def test_transmitir_si_cambia_el_perfil_a_streaming():
    r = siguiente({"uso": JUGAR, "monitor": "Un monitor común (1080p)", "transmitir": "Sí",
                   "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})
    assert r["perfil"]["clave"] == "streaming" and r["perfil"]["gpu"] is True


def test_no_se_en_el_monitor_da_1080p():
    final = siguiente({"uso": JUGAR, "monitor": "No sé", "transmitir": "No",
                       "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})
    assert final["perfil"]["clave"] == "juegos_1080p" and final["perfil"]["ram_gb"] == 16


def test_en_4k_no_pregunta_transmitir():
    r = siguiente({"uso": JUGAR, "monitor": "Un televisor o monitor 4K"})
    assert pregunta_de(r) == "multitarea"


def test_diseno_y_edicion_van_por_tipo_de_trabajo():
    r = siguiente({"uso": "Diseño o edición de video"})
    assert pregunta_de(r) == "tipo_de_trabajo"
    diseno = siguiente({"uso": "Diseño o edición de video", "tipo_de_trabajo": "Diseño (Photoshop, AutoCAD)",
                        "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})
    assert diseno["perfil"]["clave"] == "diseno" and diseno["perfil"]["gama"] == "media"
    edicion = siguiente({"uso": "Diseño o edición de video", "tipo_de_trabajo": "Edición de video",
                         "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})
    assert edicion["perfil"]["clave"] == "edicion_video" and edicion["perfil"]["gama"] == "alta"


def test_programar_es_el_perfil_programacion():
    final = siguiente({"uso": "Programar", "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})
    assert final["perfil"]["clave"] == "programacion" and final["perfil"]["ram_gb"] == 16


@pytest.mark.parametrize("respuestas, campo, valor", [
    ({"uso": OFICINA, "multitarea": "Sí, muchos", "archivos": "No tanto", "mejora": "No"}, "ram_gb", 32),
    ({"uso": OFICINA, "multitarea": "Lo normal", "archivos": "Sí, muchos", "mejora": "No"}, "disco_gb", 1000),
    ({"uso": OFICINA, "multitarea": "Lo normal", "archivos": "Sí, muchos", "mejora": "No"}, "segundo_disco", True),
    ({"uso": OFICINA, "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "Sí"}, "placa_escalable", True),
])
def test_las_respuestas_suman_requisitos_al_perfil(respuestas, campo, valor):
    assert siguiente(respuestas)["perfil"][campo] == valor


def test_respuesta_que_no_es_una_opcion_se_rechaza_con_las_opciones_validas():
    with pytest.raises(ErrorEntrevista) as error:
        siguiente({"uso": "Jugar a Fortnite"})
    assert "Oficina o estudio" in str(error.value) and "Jugar" in str(error.value)


def test_pregunta_que_no_corresponde_se_rechaza():
    with pytest.raises(ErrorEntrevista):
        siguiente({"uso": OFICINA, "monitor": "Un monitor común (1080p)"})   # oficina no pregunta monitor


def test_id_inexistente_se_rechaza():
    with pytest.raises(ErrorEntrevista):
        siguiente({"presupuesto": "2800000"})


# --- Del perfil a filtros (los usa el armado, no el modelo) -----------------------------

def test_filtros_de_oficina():
    perfil = siguiente({"uso": OFICINA, "multitarea": "Lo normal", "archivos": "No tanto", "mejora": "No"})["perfil"]
    assert filtros_del_perfil("cpu", perfil) == {"atributos": {}, "gama": "baja"}
    # 8 GB se cubren con hasta 2 unidades: cada producto tiene que traer al menos 4 GB.
    assert filtros_del_perfil("ram", perfil) == {"atributos": {"capacidad_gb__min": 4}}
    assert filtros_del_perfil("motherboard", perfil) == {"atributos": {}}
    assert filtros_del_perfil("almacenamiento_extra", perfil) == {"atributos": {}}   # sin segundo disco


def test_filtros_de_juegos_con_placa_escalable_y_segundo_disco():
    perfil = siguiente({"uso": JUGAR, "monitor": "Un monitor 2K (1440p)", "transmitir": "No",
                        "multitarea": "Sí, muchos", "archivos": "Sí, muchos", "mejora": "Sí"})["perfil"]
    assert filtros_del_perfil("gpu", perfil) == {"atributos": {}, "gama": "alta"}
    assert filtros_del_perfil("ram", perfil)["atributos"] == {"capacidad_gb__min": 16}   # 32 GB en 2 unidades
    assert filtros_del_perfil("motherboard", perfil)["atributos"] == {"ranuras_ram__min": 4, "ranuras_m2__min": 2}
    assert filtros_del_perfil("almacenamiento_extra", perfil)["atributos"] == {"capacidad_gb__min": 1000}


@pytest.mark.parametrize("capacidad, cantidad", [(32, 2), (64, 1), (16, None), (None, None)])
def test_cantidad_de_ram_para_el_perfil_de_64_gb(capacidad, cantidad):
    # Antes se pedía un solo producto de 64 GB y en el catálogo real no hay ninguno: el armado
    # premium no encontraba memoria. Ahora se cubre con hasta 2 unidades y la cuenta la hace el código.
    perfil = siguiente({"uso": JUGAR, "monitor": "Un televisor o monitor 4K", "multitarea": "Lo normal",
                        "archivos": "No tanto", "mejora": "No"})["perfil"]
    assert perfil["ram_gb"] == 64
    assert filtros_del_perfil("ram", perfil)["atributos"] == {"capacidad_gb__min": 32}
    assert cantidad_de_ram(perfil, capacidad) == cantidad


def test_todas_las_opciones_son_texto_y_los_ids_son_unicos():
    """YAML lee «No» sin comillas como False: una opción así no se puede elegir."""
    from mcp_tienda.armado.perfiles import cargar_entrevista
    preguntas = cargar_entrevista()["preguntas"]
    assert len({p["id"] for p in preguntas}) == len(preguntas)
    for pregunta in preguntas:
        assert all(isinstance(opcion, str) for opcion in pregunta["opciones"]), pregunta["id"]
