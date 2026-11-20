"""Modelos de datos compartidos por la ingesta, el servidor MCP, el agente y la interfaz.

- ProductoCrudo: lo que entrega cualquier fuente (catálogo de prueba, export, API). Es el contrato.
- ProductoCrudoAMN: lo mismo, con los campos propios del catálogo real de la tienda.
- Producto: el producto ya normalizado, con categoría propia y atributos extraídos.
- Configuracion: el armado de PC. Vive fuera del historial del chat.
- ResultadoRegla / ReporteCompatibilidad: salida de las reglas deterministas.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ValorAtributo = str | int | float | list[str] | None

Slot = Literal["cpu", "motherboard", "ram", "gpu", "almacenamiento", "almacenamiento_extra", "fuente", "gabinete",
               "cooler"]
SLOTS: tuple[str, ...] = Slot.__args__
# Lugares cuya categoría no es su propio nombre: el segundo disco es un producto de almacenamiento.
CATEGORIA_DE_LUGAR = {"almacenamiento_extra": "almacenamiento"}
# Lugares que admiten más de una unidad (dos módulos de RAM iguales, dos discos iguales).
LUGARES_CON_CANTIDAD = ("ram", "almacenamiento", "almacenamiento_extra")
CANTIDAD_MAXIMA = 4


def categoria_de_lugar(lugar: str) -> str:
    return CATEGORIA_DE_LUGAR.get(lugar, lugar)
# Los lugares obligatorios dependen de lo elegido: ver mcp_tienda/armado/reglas.py (lugares_obligatorios).


class ProductoCrudo(BaseModel):
    """Un producto tal como lo entrega la fuente, sin interpretar."""

    codigo: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    descripcion: str = ""
    categoria: str = Field(description="Categoría con el nombre que usa la fuente, sin normalizar")
    marca: str | None = None
    precio: float = Field(gt=0, description="Precio en ARS")
    stock: int = Field(ge=0)
    url: str | None = None
    imagen: str | None = None
    atributos_declarados: dict[str, ValorAtributo] = Field(
        default_factory=dict,
        description="Atributos que la fuente ya entrega como dato estructurado (no hay que leerlos del texto). "
                    "Se suman a los extraídos y, si un valor no es nulo, manda sobre el extraído.")


class ProductoCrudoAMN(ProductoCrudo):
    """Producto del catálogo real de la tienda: nombre de 40 columnas y descripción en renglones de 50.

    La ingesta lo lee con las convenciones de la tienda (ingesta/formato_amn.py) en vez del lector de texto libre.
    """

    categoria_codigo: str | None = Field(default=None, description="Código de categoría de la tienda (333 = CPU)")
    descripcion_interna: str = Field(
        default="", description="Campo hdesc: trae datos técnicos y notas del vendedor. Se lee para extraer "
                                "atributos, pero no se guarda, no se muestra y no se le pasa al modelo.")


class Producto(BaseModel):
    """Producto normalizado y con atributos extraídos, listo para buscar y armar."""

    codigo: str
    nombre: str
    descripcion: str = ""
    categoria: str = Field(description="Categoría propia (cpu, gpu, ups, cables, ...) u 'otros'")
    categoria_origen: str
    marca: str | None = None
    precio: float
    stock: int
    url: str | None = None
    imagen: str | None = None
    atributos: dict[str, ValorAtributo] = Field(default_factory=dict)

    def resumen(self) -> dict:
        """Versión corta para devolverle al LLM (sin descripción, que es texto externo largo)."""
        return {
            "codigo": self.codigo,
            "nombre": self.nombre,
            "categoria": self.categoria,
            "marca": self.marca,
            "precio": self.precio,
            "stock": self.stock,
            "atributos": {k: v for k, v in self.atributos.items() if v is not None},
        }


class Configuracion(BaseModel):
    """Un armado de PC: un producto por lugar (slot), con cantidad. El total lo calcula el código."""

    id: str | None = None
    presupuesto: float | None = None
    perfil_uso: str | None = None
    componentes: dict[Slot, Producto] = Field(default_factory=dict)
    cantidades: dict[Slot, int] = Field(default_factory=dict, description="Unidades por lugar; si falta, es 1")

    @model_validator(mode="after")
    def _categoria_coincide_con_slot(self):
        for slot, producto in self.componentes.items():
            if producto.categoria != categoria_de_lugar(slot):
                raise ValueError(
                    f"El producto {producto.codigo} es de categoría '{producto.categoria}' "
                    f"y no puede ir en el lugar '{slot}'"
                )
        for slot, cantidad in self.cantidades.items():
            if cantidad != 1 and slot not in LUGARES_CON_CANTIDAD:
                raise ValueError(f"El lugar '{slot}' lleva una sola unidad")
            if not 1 <= cantidad <= CANTIDAD_MAXIMA:
                raise ValueError(f"La cantidad de '{slot}' tiene que ser de 1 a {CANTIDAD_MAXIMA}")
        return self

    def cantidad(self, slot: str) -> int:
        return self.cantidades.get(slot, 1)

    @property
    def total(self) -> float:
        return round(sum(p.precio * self.cantidad(s) for s, p in self.componentes.items()), 2)


EstadoRegla = Literal["cumple", "no_cumple", "sin_datos"]


class ResultadoRegla(BaseModel):
    regla: str
    estado: EstadoRegla
    detalle: str
    critica: bool = Field(default=True, description="Si es crítica, «sin datos» impide confirmar el pedido")


class ReporteCompatibilidad(BaseModel):
    resultados: list[ResultadoRegla]

    @property
    def estado_general(self) -> Literal["compatible", "incompatible", "sin_confirmar"]:
        """Un «no cumple» de cualquier regla es incompatible; un «sin datos» solo cuenta en las críticas."""
        if any(r.estado == "no_cumple" for r in self.resultados):
            return "incompatible"
        if any(r.estado == "sin_datos" and r.critica for r in self.resultados):
            return "sin_confirmar"
        return "compatible"

    @property
    def avisos(self) -> list[str]:
        """Reglas no críticas que no se pudieron verificar: no bloquean, pero hay que decírselo al usuario."""
        return [f"{r.regla}: {r.detalle}" for r in self.resultados if r.estado == "sin_datos" and not r.critica]

    def como_dict(self) -> dict:
        return {
            "estado_general": self.estado_general,
            "resultados": [r.model_dump() for r in self.resultados],
            "avisos": self.avisos,
        }


class Atributo(BaseModel):
    """Definición de un atributo dentro del esquema de una categoría."""

    tipo: Literal["texto", "entero", "decimal", "lista"]
    valores: list[str] | None = None
    valores_fuera_del_armado: list[str] | None = Field(
        default=None, description="Valores reales que se guardan (para que las reglas digan «no cumple» en vez de "
                                  "«sin datos») pero que el armado no ofrece; no se listan en el prompt.")
    unidad: str | None = None
    opcional: bool = False
    descripcion: str | None = None


class Esquema(BaseModel):
    """Esquema de atributos de una categoría (datos/esquemas/<categoria>.yaml)."""

    categoria: str
    nombre: str
    sinonimos: list[str]
    atributos: dict[str, Atributo]

    @field_validator("sinonimos")
    @classmethod
    def _sin_vacios(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("cada esquema necesita al menos un sinónimo de categoría")
        return v
