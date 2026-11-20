"""Fábrica de modelos (mismo patrón que el ejemplo de la cátedra).

El agente (agente.py) solo llama a get_model(); no sabe qué proveedor hay detrás.
Para cambiar de modelo —por ejemplo, del base al afinado— se edita el .env:

    MODEL_PROVIDER=ollama        MODEL_NAME=qwen3:4b          (modelo base)
    MODEL_PROVIDER=ollama        MODEL_NAME=amn-qwen3-lora    (modelo afinado, importado con `ollama create`)
    MODEL_PROVIDER=lmstudio      MODEL_NAME=<id del modelo cargado en LM Studio>

Por defecto todo corre local: el chat y los embeddings del RAG usan Ollama o LM Studio.

Selector de modelo: además del modelo local se puede usar Gemini por API, eligiéndolo en cada
mensaje. `opciones_de_modelo()` dice cuáles hay; `get_model(opcion="gemini")` lo arma. Gemini solo
aparece si el .env tiene GOOGLE_API_KEY y GEMINI_MODEL. Los embeddings siguen siendo locales.
"""
import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

load_dotenv()

PROVEEDOR_POR_DEFECTO = "ollama"
MODELO_POR_DEFECTO = "qwen3:4b"
EMBEDDINGS_POR_DEFECTO = "bge-m3"   # multilingüe: los documentos y las consultas están en español

OPCION_LOCAL = "local"     # el modelo del .env (MODEL_PROVIDER, MODEL_NAME)
OPCION_GEMINI = "gemini"   # Gemini por API (GOOGLE_API_KEY, GEMINI_MODEL)


def gemini_configurado() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_MODEL"))


def opciones_de_modelo() -> dict[str, str]:
    """Modelos que se pueden elegir, como {opción: etiqueta para mostrar}. El local siempre está."""
    opciones = {OPCION_LOCAL: f"Local ({os.getenv('MODEL_NAME', MODELO_POR_DEFECTO)})"}
    if gemini_configurado():
        opciones[OPCION_GEMINI] = f"Gemini ({os.getenv('GEMINI_MODEL')})"
    return opciones


def es_error_de_cuota(error: BaseException) -> bool:
    """True si el proveedor rechazó el pedido por límite de uso (por ejemplo, el plan gratis de Gemini)."""
    texto = f"{type(error).__name__} {error}"
    return any(marca in texto for marca in ("429", "RESOURCE_EXHAUSTED", "ResourceExhausted", "quota"))


def es_error_transitorio(error: BaseException) -> bool:
    """True si el proveedor está saturado o caído por un rato (por ejemplo, «alta demanda» de Gemini)."""
    texto = f"{type(error).__name__} {error}"
    return any(marca in texto for marca in ("503", "UNAVAILABLE", "ServiceUnavailable", "high demand"))


def _ollama_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _lmstudio_url() -> str:
    return os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")


def get_embeddings() -> Embeddings:
    """Modelo de embeddings para el RAG: local, servido por Ollama o LM Studio."""
    provider = os.getenv("EMBEDDINGS_PROVIDER") or os.getenv("MODEL_PROVIDER", PROVEEDOR_POR_DEFECTO)
    name = os.getenv("EMBEDDINGS_MODEL", EMBEDDINGS_POR_DEFECTO)

    if provider == "lmstudio":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=name,
            base_url=_lmstudio_url(),
            api_key=SecretStr("lm-studio"),
            # LM Studio espera texto; sin esto el cliente le manda tokens ya codificados.
            check_embedding_ctx_length=False,
        )

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=name, base_url=_ollama_url())

    raise RuntimeError(
        f"EMBEDDINGS_PROVIDER={provider!r} no está soportado: usá 'ollama' o 'lmstudio' (embeddings locales)."
    )


def _modelo_gemini() -> BaseChatModel:
    if not gemini_configurado():
        raise RuntimeError("Para usar Gemini completá GOOGLE_API_KEY y GEMINI_MODEL en el .env.")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=os.environ["GEMINI_MODEL"],   # la clave la lee de GOOGLE_API_KEY
        temperature=0,
        # Gemini a veces responde 503 («alta demanda») y se recupera en segundos: se reintenta.
        # Si se agotó la cuota del plan gratis (429), reintentar no sirve y el error sube igual.
        max_retries=4,
    )


def get_model(name: str | None = None, opcion: str = OPCION_LOCAL) -> BaseChatModel:
    """Modelo de chat.

    `opcion` elige entre el modelo local del .env y Gemini (ver `opciones_de_modelo`).
    `name` fuerza un modelo local puntual (evaluación base vs. afinado).
    """
    if opcion == OPCION_GEMINI:
        return _modelo_gemini()
    if opcion != OPCION_LOCAL:
        raise ValueError(f"Modelo desconocido: {opcion!r}. Opciones: {', '.join(opciones_de_modelo())}.")

    provider = os.getenv("MODEL_PROVIDER", PROVEEDOR_POR_DEFECTO)
    name = name or os.getenv("MODEL_NAME", MODELO_POR_DEFECTO)

    if provider == "lmstudio":
        from chat_lmstudio import ChatLMStudio

        return ChatLMStudio(
            model=name,
            base_url=_lmstudio_url(),
            api_key=SecretStr("lm-studio"),   # el cliente la exige, LM Studio la ignora
            temperature=0,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        extras = {}
        if keep_alive := os.getenv("MODEL_KEEP_ALIVE"):
            extras["keep_alive"] = keep_alive
        if num_gpu := os.getenv("MODEL_NUM_GPU"):
            extras["num_gpu"] = int(num_gpu)

        return ChatOllama(
            model=name,
            base_url=_ollama_url(),
            temperature=0,
            # Ollama recorta en silencio lo que no entra en su ventana por defecto. El prompt más
            # los esquemas de las tools es largo: si se recorta, el modelo «se olvida» de las tools.
            num_ctx=int(os.getenv("MODEL_NUM_CTX", "8192")),
            # Qwen3 «piensa» antes de responder. Apagado es más rápido; MODEL_RAZONAMIENTO=1 lo
            # prende y la interfaz muestra el razonamiento.
            reasoning=os.getenv("MODEL_RAZONAMIENTO", "0") == "1",
            **extras,
        )

    return init_chat_model(name, model_provider=provider, temperature=0)
