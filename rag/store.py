"""Base vectorial del RAG: rutas y acceso compartidos por la ingesta y la tool.

Igual que en el ejemplo de la cátedra, con dos diferencias: los embeddings son locales
(model.get_embeddings) y se pueden pasar otros embeddings u otra carpeta (lo usan los tests).
"""
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from model import get_embeddings

RAG_DIR = Path(__file__).parent
DOCS_DIR = RAG_DIR / "docs"          # documentos fuente (.md / .txt)
DB_DIR = RAG_DIR / "chroma_db"       # base vectorial persistida en disco


def get_store(embeddings: Embeddings | None = None, db_dir: Path | None = None) -> Chroma:
    return Chroma(
        collection_name="conocimiento",
        embedding_function=embeddings or get_embeddings(),
        persist_directory=str(db_dir or DB_DIR),
    )
