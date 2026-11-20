"""Gama de una CPU o una GPU, por reglas. La gama no la inventa el LLM.

La fuente de verdad es la tabla del documento `rag/docs/tabla_cpu_gpu_por_gama.md`, el mismo que
indexa el RAG. Así lo que el agente explica y lo que el código aplica salen del mismo lugar.

Formato de la tabla (Markdown):

    | componente | modelo        | gama  | puntaje |
    |------------|---------------|-------|---------|
    | cpu        | Ryzen 5 5600  | media | 60      |
    | gpu        | RTX 4060 Ti   | media | 65      |

- `componente`: cpu o gpu.  `gama`: baja, media, alta o premium.  `puntaje`: número opcional para ordenar.
- `modelo` se busca como palabras completas dentro del nombre del producto, sin distinguir
  mayúsculas, tildes ni guiones. Si coinciden dos filas gana la más larga («RTX 4060 Ti» antes
  que «RTX 4060»). «Ryzen 5 5600» NO coincide con «Ryzen 5 5600G»: son modelos distintos.
- Los nombres pegados de la tienda («RTX5060TI», «GTX1650») coinciden con las filas escritas con
  espacios («RTX 5060 Ti»), igual que los requisitos de juegos («GTX 1060»).
- Si el mismo modelo aparece dos veces, manda la última fila: la sección manual del documento va
  al final, así lo que corrige el grupo pisa lo generado (ver tabla_gamas.py).

Si el modelo no está en la tabla, la gama es None («sin datos»): nunca se adivina.
"""

import os
import re
from functools import lru_cache
from pathlib import Path

from mcp_tienda.config import RAIZ
from mcp_tienda.esquemas import normalizar_texto

GAMAS = ("baja", "media", "alta", "premium")
COMPONENTES_CON_GAMA = ("cpu", "gpu")


def ruta_tabla() -> Path:
    ruta = Path(os.getenv("AMN_TABLA_GAMAS", "rag/docs/tabla_cpu_gpu_por_gama.md"))
    return ruta if ruta.is_absolute() else RAIZ / ruta


# Letras que, pegadas al número, son parte del modelo: «5060 Ti», «5600G», «12400F», «9800X3D».
_SUFIJOS = r"(ti|super|xtx|xt|x3d|gt|ge|g|f|k|kf|ks|x)"


def _normalizar(texto: str) -> str:
    """Forma comparable de un nombre: «PL.VIDEO GF RTX5060TI» y «RTX 5060 Ti» quedan igual.

    1. Minúsculas, sin tildes, y todo lo que no es letra o número pasa a ser un espacio.
    2. Las letras del principio de una palabra se separan del número: «rtx5060ti» → «rtx 5060ti»,
       «i5» → «i 5». (Solo al principio: «9800x3d» queda entero.)
    3. Un sufijo de modelo que quedó suelto se pega al número: «5060 ti» → «5060ti». Así «5600» y
       «5600g» siguen siendo palabras distintas.
    """
    texto = re.sub(r"[^a-z0-9]+", " ", normalizar_texto(texto))
    texto = re.sub(r"\b([a-z]+)(?=\d)", r"\1 ", texto)
    texto = re.sub(rf"\b(\d+) {_SUFIJOS}\b", r"\1\2", texto)
    return " ".join(texto.split())


@lru_cache(maxsize=8)
def _leer(ruta: str, _modificado: float) -> tuple[dict, ...]:
    filas: dict[tuple[str, str], dict] = {}
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        if not linea.strip().startswith("|"):
            continue
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celdas) < 3:
            continue
        componente, modelo, gama = celdas[0].lower(), _normalizar(celdas[1]), celdas[2].lower()
        if componente not in COMPONENTES_CON_GAMA or gama not in GAMAS or not modelo:
            continue   # encabezado, separador o fila incompleta
        puntaje = celdas[3] if len(celdas) > 3 else ""
        fila = {"componente": componente, "modelo": modelo, "gama": gama,
                "puntaje": float(puntaje.replace(",", ".")) if re.fullmatch(r"\d+([.,]\d+)?", puntaje) else None}
        filas[(componente, modelo)] = fila   # si se repite, manda la última (la corrección manual)
    return tuple(filas.values())


def leer_tabla(ruta: Path | None = None) -> tuple[dict, ...]:
    """Filas válidas de la tabla. Si el archivo no existe, la tabla está vacía."""
    ruta = ruta or ruta_tabla()
    if not ruta.exists():
        return ()
    return _leer(str(ruta), ruta.stat().st_mtime)   # se vuelve a leer si el archivo cambió


def buscar_fila(nombre: str, componente: str, ruta: Path | None = None) -> dict | None:
    """Fila de la tabla que corresponde a un nombre de producto (o de un requisito de un juego)."""
    texto = f" {_normalizar(nombre)} "
    candidatas = [f for f in leer_tabla(ruta) if f["componente"] == componente and f" {f['modelo']} " in texto]
    return max(candidatas, key=lambda f: len(f["modelo"])) if candidatas else None


def mismo_modelo(modelo: str, nombre: str) -> bool:
    """True si el nombre de un producto es exactamente ese modelo de CPU o GPU.

    «RTX 4060» coincide con «PL.VIDEO GF RTX4060» pero no con «RTX 4060 Ti»; «Ryzen 5 5600» no
    coincide con «5600G». La palabra «Core» no hace falta: hay nombres que la omiten.
    """
    clave = re.sub(r"^core ", "", _normalizar(modelo))
    return bool(clave) and f" {clave} " in f" {_normalizar(nombre)} "


def texto_de_busqueda(modelo: str) -> str:
    """Texto para buscar un modelo en el catálogo, escrito pegado («rtx4060») o separado («4060»).

    La búsqueda de texto es amplia (puede traer la 4060 Ti); el filtro fino lo hace mismo_modelo.
    """
    palabras = _normalizar(modelo).split()
    return f"{''.join(palabras)} {palabras[-1]}" if palabras else ""


def clasificar_gama(nombre: str, categoria: str, ruta: Path | None = None) -> str | None:
    """Gama (baja, media, alta) de un producto; None si no aplica o si no está en la tabla."""
    if categoria not in COMPONENTES_CON_GAMA:
        return None
    fila = buscar_fila(nombre, categoria, ruta)
    return fila["gama"] if fila else None
