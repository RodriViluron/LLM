"""model.py: el proveedor y el modelo salen del .env; el resto del código no se entera."""

import pytest

from model import OPCION_GEMINI, OPCION_LOCAL, es_error_de_cuota, get_embeddings, get_model, opciones_de_modelo


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for variable in ["MODEL_PROVIDER", "MODEL_NAME", "MODEL_NUM_CTX", "MODEL_RAZONAMIENTO",
                     "OLLAMA_BASE_URL", "LMSTUDIO_BASE_URL", "EMBEDDINGS_PROVIDER", "EMBEDDINGS_MODEL",
                     "GOOGLE_API_KEY", "GEMINI_MODEL"]:
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def con_gemini(monkeypatch):
    """Gemini configurado con una clave de mentira: alcanza para armar el modelo sin llamar a la API."""
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-de-prueba")


def test_sin_clave_de_gemini_solo_esta_el_modelo_local():
    assert list(opciones_de_modelo()) == [OPCION_LOCAL]
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        get_model(opcion=OPCION_GEMINI)


def test_con_clave_aparece_gemini_y_se_arma_sin_tocar_el_local(con_gemini):
    assert opciones_de_modelo() == {OPCION_LOCAL: "Local (qwen3:4b)", OPCION_GEMINI: "Gemini (gemini-de-prueba)"}
    gemini = get_model(opcion=OPCION_GEMINI)
    assert type(gemini).__name__ == "ChatGoogleGenerativeAI"
    assert gemini.model.endswith("gemini-de-prueba") and gemini.temperature == 0
    assert type(get_model()).__name__ == "ChatOllama"   # el local sigue siendo el de siempre


def test_gemini_acepta_los_esquemas_de_todas_las_tools(con_gemini, cliente):
    """Gemini es más estricto con los esquemas de las tools: tienen que poder convertirse."""
    from tools import crear_tools

    tools = crear_tools(cliente)
    get_model(opcion=OPCION_GEMINI).bind_tools(tools)   # falla acá si algún esquema no se puede convertir


def test_opcion_desconocida():
    with pytest.raises(ValueError, match="desconocido"):
        get_model(opcion="otro")


def test_errores_de_cuota():
    assert es_error_de_cuota(RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert not es_error_de_cuota(RuntimeError("se cortó la conexión"))


def test_por_defecto_ollama_con_contexto_explicito():
    modelo = get_model()
    assert type(modelo).__name__ == "ChatOllama"
    assert modelo.model == "qwen3:4b"
    assert modelo.num_ctx == 8192
    assert modelo.temperature == 0
    assert modelo.reasoning is False


def test_cambiar_al_modelo_afinado_es_solo_cambiar_el_env(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "amn-qwen3-lora")
    monkeypatch.setenv("MODEL_NUM_CTX", "4096")
    modelo = get_model()
    assert modelo.model == "amn-qwen3-lora" and modelo.num_ctx == 4096


def test_nombre_explicito_gana_al_env(monkeypatch):
    """Lo usa la evaluación para comparar base contra afinado en la misma corrida."""
    monkeypatch.setenv("MODEL_NAME", "amn-qwen3-lora")
    assert get_model("qwen3:4b").model == "qwen3:4b"


def test_lmstudio(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "lmstudio")
    monkeypatch.setenv("MODEL_NAME", "qwen3-4b")
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:4321/v1")
    modelo = get_model()
    assert type(modelo).__name__ == "ChatLMStudio"
    assert modelo.model_name == "qwen3-4b"
    assert str(modelo.openai_api_base) == "http://localhost:4321/v1"


def test_embeddings_locales_siguen_al_proveedor(monkeypatch):
    assert type(get_embeddings()).__name__ == "OllamaEmbeddings"
    assert get_embeddings().model == "bge-m3"
    monkeypatch.setenv("MODEL_PROVIDER", "lmstudio")
    embeddings = get_embeddings()
    assert type(embeddings).__name__ == "OpenAIEmbeddings"
    assert embeddings.check_embedding_ctx_length is False


def test_embeddings_no_aceptan_proveedor_en_la_nube(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "google_genai")
    with pytest.raises(RuntimeError, match="locales"):
        get_embeddings()
