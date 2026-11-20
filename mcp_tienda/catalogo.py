"""Catálogo local en SQLite: es lo único que consultan el agente y el servidor MCP.

- Tabla `productos`: datos normalizados; los atributos van como JSON.
- Tabla virtual `productos_fts` (FTS5): búsqueda de texto sin tildes, ordenada por BM25.
La búsqueda semántica con embeddings se agrega en la Fase 2.
"""

import json
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from mcp_tienda.config import ruta_catalogo_db
from mcp_tienda.esquemas import cargar_esquemas, normalizar_texto
from mcp_tienda.modelos import Producto

ESQUEMA_SQL = """
CREATE TABLE productos (
    codigo TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    categoria TEXT NOT NULL,
    categoria_origen TEXT NOT NULL,
    marca TEXT,
    precio REAL NOT NULL,
    stock INTEGER NOT NULL,
    url TEXT,
    imagen TEXT,
    atributos TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_productos_categoria ON productos(categoria);
CREATE VIRTUAL TABLE productos_fts USING fts5(
    codigo UNINDEXED, nombre, descripcion, marca, categoria,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

# Peso de cada columna en BM25 (codigo, nombre, descripcion, marca, categoria): el nombre pesa más.
PESOS_BM25 = "0.0, 10.0, 2.0, 3.0, 3.0"
LIMITE_MAXIMO = 2000   # más que cualquier categoría del catálogo real (4 a 9 mil productos en total)

PALABRAS_VACIAS = set(
    "a al algo con de del el en es la las lo los mi mis para por que quiero un una unos unas y o "
    "necesito busco buscando tenes tienen hay me sirva sirve como esta este esto".split()
)


class FiltroInvalido(ValueError):
    """Filtro con un atributo que no existe en el esquema."""


def _consulta_fts(texto: str, operador: str = "OR") -> str | None:
    """Pasa el texto del usuario a una consulta FTS5: palabras útiles, con prefijo.

    `operador` es "AND" (tienen que estar todas las palabras) u "OR" (alcanza con una).
    """
    terminos = []
    for palabra in re.findall(r"\w+", normalizar_texto(texto)):
        if palabra in PALABRAS_VACIAS:
            continue
        if len(palabra) > 4 and palabra.endswith("es"):
            palabra = palabra[:-2]
        elif len(palabra) > 4 and palabra.endswith("s"):
            palabra = palabra[:-1]
        terminos.append(f'"{palabra}"*')
    return f" {operador} ".join(dict.fromkeys(terminos)) or None


class Catalogo:
    def __init__(self, ruta_db: Path | None = None):
        self.ruta_db = Path(ruta_db or ruta_catalogo_db())

    def _conectar(self) -> sqlite3.Connection:
        if not self.ruta_db.exists():
            raise FileNotFoundError(
                f"No existe {self.ruta_db}. Corré primero: uv run python -m mcp_tienda.ingesta.cargar --fuente prueba"
            )
        conn = sqlite3.connect(self.ruta_db)
        conn.row_factory = sqlite3.Row
        return conn

    # --- Escritura (la usa la ingesta) ---------------------------------------------------------

    def recrear(self, productos: Iterable[Producto]) -> int:
        """Borra la base y la vuelve a crear con estos productos."""
        self.ruta_db.parent.mkdir(parents=True, exist_ok=True)
        self.ruta_db.unlink(missing_ok=True)
        conn = sqlite3.connect(self.ruta_db)
        with conn:
            conn.executescript(ESQUEMA_SQL)
            n = 0
            for p in productos:
                conn.execute(
                    "INSERT INTO productos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (p.codigo, p.nombre, p.descripcion, p.categoria, p.categoria_origen, p.marca,
                     p.precio, p.stock, p.url, p.imagen, json.dumps(p.atributos, ensure_ascii=False)),
                )
                conn.execute(
                    "INSERT INTO productos_fts VALUES (?,?,?,?,?)",
                    (p.codigo, p.nombre, p.descripcion, p.marca or "", p.categoria),
                )
                n += 1
        conn.close()
        return n

    # --- Lectura -------------------------------------------------------------------------------

    @staticmethod
    def _a_producto(fila: sqlite3.Row) -> Producto:
        datos = dict(fila)
        datos["atributos"] = json.loads(datos["atributos"])
        return Producto.model_validate(datos)

    def obtener(self, codigo: str) -> Producto | None:
        with self._conectar() as conn:
            fila = conn.execute("SELECT * FROM productos WHERE codigo = ?", (codigo.strip(),)).fetchone()
        return self._a_producto(fila) if fila else None

    def buscar(
        self,
        texto: str | None = None,
        categoria: str | None = None,
        precio_min: float | None = None,
        precio_max: float | None = None,
        marca: str | None = None,
        solo_con_stock: bool = True,
        atributos: dict | None = None,
        limite: int = 10,
    ) -> list[Producto]:
        """Busca combinando filtros estructurados y texto.

        `atributos` filtra por atributos extraídos. Igualdad: {"socket": "AM4"}. Rango numérico:
        sufijos `__min` y `__max`, p. ej. {"potencia_w__min": 650}. En atributos de tipo lista
        (formatos_admitidos, sockets) la igualdad significa «contiene».
        Sufijo `__en` para aceptar varios valores: {"formato__en": ["ATX", "Micro-ATX"]}.
        """
        condiciones, parametros = self._condiciones(categoria, precio_min, precio_max, marca, solo_con_stock)
        for clave, valor in (atributos or {}).items():
            sql, params = self._condicion_atributo(clave, valor, categoria)
            condiciones.append(sql)
            parametros += params
        donde = (" AND " + " AND ".join(condiciones)) if condiciones else ""
        # Tope de seguridad. El servidor MCP le muestra al modelo como mucho 20; pide más solo cuando
        # filtra después de buscar (gama, compatibilidad) y necesita todos los candidatos.
        limite = max(1, min(int(limite), LIMITE_MAXIMO))

        with self._conectar() as conn:
            if not (texto and _consulta_fts(texto)):
                sql = f"SELECT p.* FROM productos p WHERE 1=1{donde} ORDER BY p.precio LIMIT ?"
                filas = conn.execute(sql, [*parametros, limite]).fetchall()
            else:
                # Primero los productos que tienen TODAS las palabras; si no alcanzan, se completa
                # con los que tienen alguna. Así «fuente corsair» no trae antes un gabinete Corsair.
                sql = (f"SELECT p.* FROM productos p JOIN productos_fts f ON f.codigo = p.codigo "
                       f"WHERE productos_fts MATCH ?{donde} "
                       f"ORDER BY bm25(productos_fts, {PESOS_BM25}), p.precio LIMIT ?")
                filas, vistos = [], set()
                for operador in ("AND", "OR"):
                    for fila in conn.execute(sql, [_consulta_fts(texto, operador), *parametros, limite]):
                        if fila["codigo"] not in vistos and len(filas) < limite:
                            vistos.add(fila["codigo"])
                            filas.append(fila)
                    if len(filas) >= limite:
                        break
        return [self._a_producto(f) for f in filas]

    @staticmethod
    def _condiciones(categoria, precio_min, precio_max, marca, solo_con_stock) -> tuple[list[str], list]:
        condiciones, parametros = [], []
        if categoria:
            condiciones.append("p.categoria = ?")
            parametros.append(categoria)
        if precio_min is not None:
            condiciones.append("p.precio >= ?")
            parametros.append(precio_min)
        if precio_max is not None:
            condiciones.append("p.precio <= ?")
            parametros.append(precio_max)
        if marca:
            condiciones.append("lower(p.marca) = lower(?)")
            parametros.append(marca)
        if solo_con_stock:
            condiciones.append("p.stock > 0")
        return condiciones, parametros

    def contar_sin_dato(
        self,
        atributos: dict | None,
        categoria: str | None = None,
        precio_min: float | None = None,
        precio_max: float | None = None,
        marca: str | None = None,
        solo_con_stock: bool = True,
    ) -> int:
        """Cuántos productos quedan fuera de un filtro por atributos porque NO informan el dato.

        No es que no cumplan: no se sabe. El agente tiene que poder decírselo al usuario.
        """
        nombres = list(dict.fromkeys(clave.partition("__")[0] for clave in (atributos or {})))
        if not nombres:
            return 0
        for clave, valor in atributos.items():
            self._condicion_atributo(clave, valor, categoria)   # valida nombres y operadores
        condiciones, parametros = self._condiciones(categoria, precio_min, precio_max, marca, solo_con_stock)
        nulos = " OR ".join("json_extract(p.atributos, ?) IS NULL" for _ in nombres)
        condiciones.append(f"({nulos})")
        parametros += [f"$.{n}" for n in nombres]
        if categoria is None:
            # Sin categoría, solo cuentan las categorías que tienen ese atributo en su esquema.
            con_atributo = [c for c, e in cargar_esquemas().items() if any(n in e.atributos for n in nombres)]
            condiciones.append(f"p.categoria IN ({','.join('?' * len(con_atributo))})")
            parametros += con_atributo
        sql = "SELECT count(*) FROM productos p WHERE " + " AND ".join(condiciones)
        with self._conectar() as conn:
            return conn.execute(sql, parametros).fetchone()[0]

    @staticmethod
    def _condicion_atributo(clave: str, valor, categoria: str | None) -> tuple[str, list]:
        nombre, _, operador = clave.partition("__")
        esquemas = cargar_esquemas()
        candidatos = [esquemas[categoria]] if categoria in esquemas else list(esquemas.values())
        definiciones = [e.atributos[nombre] for e in candidatos if nombre in e.atributos]
        if not definiciones:
            raise FiltroInvalido(f"El atributo '{nombre}' no existe para la categoría '{categoria}'")
        if operador not in ("", "min", "max", "en"):
            raise FiltroInvalido(f"Operador '{operador}' no válido: usá __min, __max o __en")
        definicion = definiciones[0]
        ruta = f"$.{nombre}"  # seguro: `nombre` ya se validó contra el esquema
        if operador == "en":
            valores = [str(v).lower() for v in (valor if isinstance(valor, list) else [valor])]
            marcas = ",".join("?" * len(valores))
            return f"lower(json_extract(p.atributos, ?)) IN ({marcas})", [ruta, *valores]
        if definicion.tipo == "lista":
            return ("EXISTS (SELECT 1 FROM json_each(p.atributos, ?) WHERE lower(value) = lower(?))",
                    [ruta, str(valor)])
        if definicion.tipo in ("entero", "decimal"):
            if operador == "min":
                return "json_extract(p.atributos, ?) >= ?", [ruta, float(valor)]
            if operador == "max":
                return "json_extract(p.atributos, ?) <= ?", [ruta, float(valor)]
            return "abs(json_extract(p.atributos, ?) - ?) < 0.01", [ruta, float(valor)]
        return "lower(json_extract(p.atributos, ?)) = lower(?)", [ruta, str(valor)]

    def contar_por_categoria(self) -> dict[str, int]:
        with self._conectar() as conn:
            filas = conn.execute(
                "SELECT categoria, count(*) FROM productos GROUP BY categoria ORDER BY categoria"
            ).fetchall()
        return {c: n for c, n in filas}
