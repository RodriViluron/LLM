"""Ingesta del RAG: documentos -> chunks -> embeddings -> Chroma.

Se ejecuta una vez (y de nuevo cada vez que cambien los documentos), desde la
carpeta del proyecto:   python -m rag.ingest

Parecida a la del ejemplo de la cátedra. Lo que cambia:
- Los comentarios HTML de los documentos (las indicaciones «escribir acá») no se indexan, y un
  documento que todavía no tiene contenido se saltea con un aviso.
- **Se corta por sección** (problema 5). Cortar cada 1000 caracteres mezclaba gamas en un mismo
  fragmento («Reparto en gama baja» terminaba con la gama media) y dejaba filas de tabla sin título;
  el embedding de un fragmento así queda «entre dos gamas». Ahora cada sección de Markdown es un
  fragmento (si es muy larga se subdivide), empieza con «documento › sección» y lleva en la metadata
  la gama de su sección (`gama`: baja, media, alta, premium o general), para que la tool pueda filtrar.
"""
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from mcp_tienda.armado.gamas import GAMAS
from rag.store import DB_DIR, DOCS_DIR, get_store

MINIMO_DE_CONTENIDO = 200   # caracteres de texto propio para considerar que un documento está escrito
ENCABEZADOS = [("#", "titulo"), ("##", "seccion"), ("###", "subseccion")]
GAMA_GENERAL = "general"    # fragmentos que no son de una sola gama


def gama_de_seccion(*titulos: str) -> str:
    """La gama que nombra el título de la sección; «general» si no nombra ninguna o nombra varias."""
    texto = " ".join(t for t in titulos if t).lower()
    nombradas = [g for g in GAMAS if re.search(rf"\bgama {g}\b", texto)]
    return nombradas[0] if len(nombradas) == 1 else GAMA_GENERAL


def partir_por_secciones(documento: Document, chunk_size: int = 1000, chunk_overlap: int = 150) -> list[Document]:
    """Un fragmento por sección, con «documento › sección › subsección» al principio y la gama en la metadata."""
    secciones = MarkdownHeaderTextSplitter(ENCABEZADOS, strip_headers=True).split_text(documento.page_content)
    subdividir = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    fragmentos = []
    for seccion in secciones:
        titulos = [seccion.metadata.get(nombre) for _, nombre in ENCABEZADOS]
        contexto = " › ".join(t for t in titulos if t)
        gama = gama_de_seccion(seccion.metadata.get("seccion", ""), seccion.metadata.get("subseccion", ""))
        for pieza in subdividir.split_text(seccion.page_content):
            if not pieza.strip():
                continue
            fragmentos.append(Document(page_content=f"{contexto}\n\n{pieza}" if contexto else pieza,
                                       metadata={**documento.metadata, "seccion": contexto, "gama": gama}))
    return fragmentos


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"<!--.*?-->", "", texto, flags=re.S)


def _contenido_propio(texto: str) -> str:
    """El texto sin títulos, encabezado (líneas con >), separadores ni filas de tabla vacías."""
    lineas = []
    for linea in _sin_comentarios(texto).splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith(("#", ">")) or re.fullmatch(r"[|\s:-]+", limpia):
            continue
        lineas.append(limpia)
    return "\n".join(lineas)


def cargar_documentos(docs_dir: Path | None = None) -> tuple[list[Document], list[str]]:
    """Devuelve (documentos con contenido, nombres de los que todavía están vacíos)."""
    docs_dir = docs_dir or DOCS_DIR
    archivos = [p for p in sorted(docs_dir.iterdir()) if p.suffix in {".md", ".txt"}]
    if not archivos:
        raise SystemExit(f"No hay archivos .md o .txt en {docs_dir}")
    documentos, vacios = [], []
    for p in archivos:
        texto = p.read_text(encoding="utf-8")
        if len(_contenido_propio(texto)) < MINIMO_DE_CONTENIDO:
            vacios.append(p.name)
            continue
        # 1. Cargar: cada archivo es un Document, con su nombre como metadata.
        documentos.append(Document(page_content=_sin_comentarios(texto), metadata={"source": p.name}))
    return documentos, vacios


def ingestar(docs_dir: Path | None = None, embeddings: Embeddings | None = None, db_dir: Path | None = None) -> dict:
    documentos, vacios = cargar_documentos(docs_dir)
    if not documentos:
        raise SystemExit("Ningún documento tiene contenido todavía: escribí los archivos de rag/docs/ "
                         f"y volvé a ejecutar. Vacíos: {', '.join(vacios)}")

    # 2. Chunking por sección: la metadata del documento se hereda y se suman la sección y su gama.
    chunks = [c for d in documentos for c in partir_por_secciones(d)]

    # 3 y 4. Embeddings + base vectorial. Se reinicia la colección para no duplicar.
    store = get_store(embeddings, db_dir)
    store.reset_collection()
    store.add_documents(chunks)
    return {"documentos": len(documentos), "chunks": len(chunks), "vacios": vacios, "db": str(db_dir or DB_DIR)}


def main() -> None:
    r = ingestar()
    print(f"{r['documentos']} documentos -> {r['chunks']} chunks indexados en {r['db']}")
    if r["vacios"]:
        print(f"Sin contenido todavía (no se indexaron): {', '.join(r['vacios'])}")


if __name__ == "__main__":
    main()
