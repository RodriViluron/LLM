"""Interpreta el monto que escribe el usuario y lo compara con la escala de la tienda (problema 31).

- `interpretar_monto("2 palos")` → {"monto": 2000000, "moneda": "ARS", ...}. «Palo» es un millón,
  «luca» o «mil» es mil, «k» es mil. Acepta el formato argentino: «2.800.000» y «2,8».
- Los dólares no se convierten (no hay cotización): se devuelve moneda USD y monto None.
- «M» pegada al número es millón («2,8M»), «y medio» suma la mitad de la unidad y los números en
  palabras cuentan si van justo antes de la unidad («dos palos», «quinientas lucas»).
- Un número chico sin unidad («20») es ambiguo: puede ser 20 pesos o 20 mil. No se adivina.
- Dos montos distintos («entre 1 y 2 millones») también son ambiguos: se pregunta cuál.
- `evaluar_presupuesto` dice qué gama entra en el monto, o cuánto hace falta como mínimo.
"""

import re

MULTIPLICADORES = (
    (r"\b(palos?|mill[oó]n(es)?)\b|\d\s?m\b", 1_000_000),   # «2,8M» o «2.8 M»: la M pegada al número
    (r"\b(lucas?|mil)\b|k\b", 1_000),
)
PATRON_DOLARES = re.compile(r"u\$s|us\$|\busd\b|d[oó]lar(es)?", re.IGNORECASE)
PATRON_NUMERO = re.compile(r"\d[\d.,]*\d|\d")
PATRON_MEDIO = re.compile(r"\by\s+medi[oa]\b", re.IGNORECASE)
UMBRAL_AMBIGUO = 10_000   # por debajo de esto, un número sin unidad no se toma como pesos

# Números escritos en palabras. Solo cuentan si van justo antes de la unidad («dos palos»), para que
# «una» en «tengo una idea» no se tome como monto.
NUMEROS_EN_PALABRAS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "cien": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400,
    "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600,
    "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
}
PATRON_PALABRA_ANTES_DE_UNIDAD = re.compile(
    r"\b(" + "|".join(NUMEROS_EN_PALABRAS) + r")\s+(palos?|mill[oó]n(es)?|lucas?|mil)\b", re.IGNORECASE)


def _valor(crudo: str) -> float:
    """«2.800.000» → 2800000; «2,8» → 2.8; «2800000» → 2800000."""
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", crudo):   # separador de miles
        return float(crudo.replace(".", ""))
    if re.fullmatch(r"\d+(\.\d{3})*,\d+", crudo):    # «2.800.000,50»: miles con punto y decimales con coma
        return float(crudo.replace(".", "").replace(",", "."))
    return float(crudo.replace(",", "."))


def _numeros(texto: str) -> list[float]:
    """Todos los números del texto, en cifras o en palabras justo antes de la unidad."""
    numeros = [_valor(m.group(0)) for m in PATRON_NUMERO.finditer(texto)]
    if not numeros:
        numeros = [float(NUMEROS_EN_PALABRAS[m.group(1).lower()])
                   for m in PATRON_PALABRA_ANTES_DE_UNIDAD.finditer(texto)]
    return numeros


def _multiplicador(texto: str) -> int:
    for patron, valor in MULTIPLICADORES:
        if re.search(patron, texto, re.IGNORECASE):
            return valor
    return 1


def interpretar_monto(texto: str) -> dict | None:
    """Pasa el texto del usuario a un monto. None si no hay ningún monto en el texto."""
    if PATRON_DOLARES.search(texto):
        return {"monto": None, "moneda": "USD",
                "motivo": "El monto está en dólares y no hay cotización: no se puede comparar con la escala en pesos."}
    multiplicador = _multiplicador(texto)
    medio = 0.5 if multiplicador != 1 and PATRON_MEDIO.search(texto) else 0
    numeros = _numeros(texto)
    if not numeros:
        # «mil» o «palo y medio»: la unidad sola vale una vez.
        if multiplicador != 1:
            return {"monto": int(round((1 + medio) * multiplicador)), "moneda": "ARS", "motivo": None}
        return None
    if len(numeros) > 1:
        # Dos montos («entre 1 y 2 millones»): la unidad se aplica a los números chicos. Si dan distinto, se pregunta.
        candidatos = list(dict.fromkeys(
            int(round(n * multiplicador)) if n < UMBRAL_AMBIGUO else int(round(n)) for n in numeros))
        if len(candidatos) > 1:
            return {"monto": None, "moneda": "ARS", "ambiguo": True, "candidatos": candidatos,
                    "motivo": "El texto tiene más de un monto: hay que preguntar cuál es el presupuesto."}
        return {"monto": candidatos[0], "moneda": "ARS", "motivo": None}
    numero = numeros[0]
    if multiplicador == 1 and numero < UMBRAL_AMBIGUO:
        return {"monto": None, "moneda": "ARS", "ambiguo": True, "candidatos": [int(numero), int(numero * 1_000)],
                "motivo": "No queda claro si es en pesos o en miles: hay que preguntar."}
    return {"monto": int(round((numero + medio) * multiplicador)), "moneda": "ARS", "motivo": None}


def evaluar_presupuesto(monto: int, escala: list[dict]) -> dict:
    """Qué gama entra en el monto, según la escala del reparto (agente.escala_de_presupuesto)."""
    if not escala:
        return {"alcanza": None, "gama": None, "minimo": None,
                "motivo": "No hay escala de referencia: no se puede comparar el monto."}
    minimo = min(g["desde"] for g in escala)
    if monto < minimo:
        return {"alcanza": False, "gama": None, "minimo": minimo,
                "motivo": f"Con ese monto no alcanza para una PC completa: lo más barato cuesta cerca de ${minimo:,}."
                          .replace(",", ".")}
    entran = [g for g in escala if monto >= g["desde"]]
    return {"alcanza": True, "gama": entran[-1]["gama"], "minimo": minimo, "motivo": None}
