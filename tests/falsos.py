"""Modelo falso para probar el agente sin LLM: devuelve, en orden, las respuestas que se le cargan."""

import re
import zlib

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class ModeloFalso(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def llamada(nombre: str, args: dict, id_: str = "c1") -> AIMessage:
    """Mensaje del «modelo» que pide ejecutar una tool."""
    return AIMessage(content="", tool_calls=[{"name": nombre, "args": args, "id": id_}])


def buscar(lugar: str, id_: str | None = None) -> AIMessage:
    """El «modelo» busca una categoría entera antes de agregar una pieza.

    agregar_o_reemplazar_componente solo acepta códigos que ya aparecieron en la conversación
    (problema 20): por eso los guiones de los tests buscan antes de agregar, como el modelo real.
    """
    return llamada("buscar_productos", {"categoria": lugar, "solo_con_stock": False, "limite": 20},
                   id_ or f"b-{lugar}")


def texto(contenido: str) -> AIMessage:
    return AIMessage(content=contenido)


def modelo_con(*mensajes: AIMessage) -> ModeloFalso:
    return ModeloFalso(messages=iter(mensajes))


class EmbeddingsDePalabras(Embeddings):
    """Embeddings falsos y deterministas: cada palabra suma en una posición del vector.

    Dos textos que comparten palabras quedan cerca. Alcanza para probar la ingesta y la tool del
    RAG sin un servidor de embeddings.
    """

    TAMANIO = 512

    def _vector(self, texto: str) -> list[float]:
        vector = [0.0] * self.TAMANIO
        for palabra in re.findall(r"[a-záéíóúñ0-9]{4,}", texto.lower()):
            vector[zlib.crc32(palabra.encode()) % self.TAMANIO] += 1.0
        norma = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norma for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
