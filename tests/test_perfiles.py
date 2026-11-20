"""Paso 8 (problema 6) y problema 26: perfiles de uso y guía de preguntas en datos/entrevista_armado.yaml.

El archivo es la única fuente de «uso → gama». La sección «Perfiles de uso» del documento del RAG se
genera desde acá, así lo que el agente explica y lo que usa la entrevista dicen lo mismo.
"""

from mcp_tienda.armado.gamas import GAMAS
from mcp_tienda.armado.perfiles import (
    MARCA_FIN,
    MARCA_INICIO,
    bloque_de_perfiles,
    cargar_entrevista,
    escribir_perfiles_en_documento,
)

COMPONENTES = {"cpu", "gpu", "ram", "disco", "motherboard", "fuente", "gabinete", "cooler"}


def test_el_archivo_real_es_coherente():
    entrevista = cargar_entrevista()
    perfiles, preguntas = entrevista["perfiles"], entrevista["preguntas"]
    assert perfiles and preguntas
    for clave, p in perfiles.items():
        assert p["gama"] in GAMAS, clave
        assert p["ram_gb"] > 0 and isinstance(p["gpu"], bool), clave
        assert set(p["pesa_mas"]) <= COMPONENTES, clave
    ids = {q["id"] for q in preguntas}
    for q in preguntas:
        assert 2 <= len(q["opciones"]) <= 4, q["id"]          # preguntar_al_usuario admite de 2 a 4 botones
        for implica in q["opciones"].values():
            if "perfil" in implica:
                assert implica["perfil"] in perfiles, (q["id"], implica)
            if "sigue" in implica:
                assert implica["sigue"] in ids, (q["id"], implica)
        assert set(q.get("solo_si_perfil", [])) <= set(perfiles), q["id"]


def test_el_bloque_tiene_una_seccion_por_perfil_con_su_gama():
    entrevista = {"estado": "borrador", "perfiles": {
        "oficina": {"nombre": "Oficina y estudio", "gama": "baja", "ram_gb": 8, "gpu": False,
                    "pesa_mas": ["disco", "ram"], "alcanza_para": "navegar", "no_alcanza_para": "jugar",
                    "ejemplos": ["Word"]},
        "juegos_1080p": {"nombre": "Juegos en 1080p", "gama": "media", "ram_gb": 16, "gpu": True,
                         "pesa_mas": ["gpu"], "alcanza_para": "jugar en 1080p", "no_alcanza_para": "4K",
                         "ejemplos": ["Fortnite"]},
    }, "preguntas": []}
    bloque = bloque_de_perfiles(entrevista)
    assert "### Perfil Oficina y estudio: gama baja" in bloque
    assert "### Perfil Juegos en 1080p: gama media" in bloque
    assert "sin placa de video (usa el video integrado del procesador)" in bloque
    assert "16 GB de RAM" in bloque and "Fortnite" in bloque
    assert "borrador" in bloque.lower()


def test_escribir_reemplaza_solo_el_bloque_generado(tmp_path):
    ruta = tmp_path / "caracteristicas_por_actividad.md"
    ruta.write_text(f"# Doc\n\n## Juegos\n\nTexto a mano.\n\n## Perfiles de uso\n\n{MARCA_INICIO}\nviejo\n"
                    f"{MARCA_FIN}\n\n## Después\n\nOtro texto a mano.\n", encoding="utf-8")
    escribir_perfiles_en_documento(ruta)
    texto = ruta.read_text(encoding="utf-8")
    assert "Texto a mano." in texto and "Otro texto a mano." in texto
    assert "viejo" not in texto and "### Perfil Edición de video: gama alta" in texto


def test_sin_marcas_agrega_la_seccion_al_final(tmp_path):
    ruta = tmp_path / "c.md"
    ruta.write_text("# Doc\n\nTexto.\n", encoding="utf-8")
    escribir_perfiles_en_documento(ruta)
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith("# Doc\n\nTexto.") and "## Perfiles de uso" in texto and MARCA_INICIO in texto
