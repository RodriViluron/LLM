"""Ingesta: fuente → normalización de categoría → extracción de atributos → SQLite.

Uso:
    python -m mcp_tienda.ingesta.cargar --fuente prueba
    python -m mcp_tienda.ingesta.cargar --fuente csv --archivo datos/catalogo_real/export.csv
    python -m mcp_tienda.ingesta.cargar --fuente api          (necesita AMN_API_URL y AMN_API_COOKIE)
"""

import argparse
from collections import Counter
from pathlib import Path

from mcp_tienda.catalogo import Catalogo
from mcp_tienda.esquemas import normalizar_categoria
from mcp_tienda.ingesta import formato_amn
from mcp_tienda.ingesta.extraccion import extraer_atributos
from mcp_tienda.ingesta.fuentes import FuenteCatalogo, obtener_fuente
from mcp_tienda.modelos import SLOTS, Producto, ProductoCrudo, ProductoCrudoAMN


def _procesar_amn(crudo: ProductoCrudoAMN) -> tuple[str, str, dict]:
    """Catálogo real de la tienda: devuelve (categoría, descripción para guardar, atributos).

    Las piezas del armado se reconocen y se leen con las convenciones de la tienda (formato_amn).
    El resto usa la búsqueda de categoría por nombre y el lector de texto libre, pero NUNCA puede
    caer en una categoría del armado: un cargador de notebook que está en «Fuentes» no es una
    fuente de PC, y si lo fuera el armado lo podría ofrecer.
    """
    descripcion = formato_amn.descripcion_publica(crudo.descripcion)
    lectura = formato_amn.leer(crudo.nombre, crudo.descripcion, crudo.descripcion_interna, crudo.categoria_codigo)
    if lectura.categoria:
        return lectura.categoria, descripcion, lectura.atributos
    categoria = normalizar_categoria(crudo.categoria)
    if categoria in SLOTS:
        return "otros", descripcion, {}
    return categoria, descripcion, extraer_atributos(categoria, crudo.nombre, descripcion)


def procesar(crudo: ProductoCrudo) -> Producto:
    if isinstance(crudo, ProductoCrudoAMN):
        categoria, descripcion, atributos = _procesar_amn(crudo)
    else:
        categoria = normalizar_categoria(crudo.categoria)
        descripcion = crudo.descripcion
        atributos = extraer_atributos(categoria, crudo.nombre, crudo.descripcion)
    # Lo que la fuente entrega como dato estructurado manda sobre lo leído del texto.
    atributos = atributos | {k: v for k, v in crudo.atributos_declarados.items() if v is not None}
    return Producto(
        codigo=crudo.codigo, nombre=crudo.nombre, descripcion=descripcion,
        categoria=categoria, categoria_origen=crudo.categoria, marca=crudo.marca,
        precio=crudo.precio, stock=crudo.stock, url=crudo.url, imagen=crudo.imagen,
        atributos=atributos,
    )


def cargar(fuente: FuenteCatalogo, ruta_db: Path | None = None) -> dict:
    productos = [procesar(c) for c in fuente.iterar_productos()]
    catalogo = Catalogo(ruta_db)
    catalogo.recrear(productos)
    con_dato = Counter()
    total_attr = Counter()
    for p in productos:
        for valor in p.atributos.values():
            total_attr[p.categoria] += 1
            con_dato[p.categoria] += valor is not None
    return {
        "ruta_db": str(catalogo.ruta_db),
        "productos": len(productos),
        "por_categoria": dict(Counter(p.categoria for p in productos)),
        "cobertura_atributos": {c: con_dato[c] / total_attr[c] for c in total_attr},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga el catálogo en SQLite")
    parser.add_argument("--fuente", default="prueba", choices=["prueba", "csv", "api"])
    parser.add_argument("--archivo", help="ruta del CSV (solo para --fuente csv)")
    parser.add_argument("--db", type=Path, help="ruta de la base (por defecto AMN_CATALOGO_DB)")
    args = parser.parse_args()

    resumen = cargar(obtener_fuente(args.fuente, args.archivo), args.db)
    print(f"Cargados {resumen['productos']} productos en {resumen['ruta_db']}")
    for categoria, n in sorted(resumen["por_categoria"].items()):
        cobertura = resumen["cobertura_atributos"].get(categoria)
        extra = f"  atributos con dato: {cobertura:.0%}" if cobertura is not None else ""
        print(f"  {categoria:16} {n:4}{extra}")


if __name__ == "__main__":
    main()
