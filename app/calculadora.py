"""Lógica de negocio para el cálculo de notas definitivas.

Reglas:
- Una nota válida es un número (int o float) entre 0.0 y 5.0 inclusive.
- Pesos: Momento 1 = 30 %, Momento 2 = 30 %, Momento 3 = 40 %.
- La definitiva se redondea a 2 decimales.
- Estado: < 2.0 REPROBADO; [2.0, 3.0) HABILITA; >= 3.0 APROBADO.
"""

NOTA_MINIMA = 0.0
NOTA_MAXIMA = 5.0

PESO_MOMENTO_1 = 0.30
PESO_MOMENTO_2 = 0.30
PESO_MOMENTO_3 = 0.40

LIMITE_HABILITA = 2.0
LIMITE_APROBADO = 3.0

ESTADO_APROBADO = "APROBADO"
ESTADO_HABILITA = "HABILITA"
ESTADO_REPROBADO = "REPROBADO"


def _es_numero(valor):
    """Indica si el valor es int o float, excluyendo booleanos.

    En Python bool hereda de int (True == 1), por eso se excluye explícitamente.
    """
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def validar_nota(nota):
    """Valida una nota y la devuelve como float.

    Raises:
        TypeError: si la nota es None, booleano o no numérica.
        ValueError: si la nota está fuera del rango [0.0, 5.0].
    """
    if not _es_numero(nota):
        raise TypeError(f"La nota debe ser numérica, se recibió {type(nota).__name__}")
    if not NOTA_MINIMA <= nota <= NOTA_MAXIMA:
        raise ValueError(
            f"La nota debe estar entre {NOTA_MINIMA} y {NOTA_MAXIMA}, se recibió {nota}"
        )
    return float(nota)


def calcular_definitiva(m1, m2, m3):
    """Calcula la nota definitiva ponderada y redondeada a 2 decimales."""
    nota1 = validar_nota(m1)
    nota2 = validar_nota(m2)
    nota3 = validar_nota(m3)
    definitiva = nota1 * PESO_MOMENTO_1 + nota2 * PESO_MOMENTO_2 + nota3 * PESO_MOMENTO_3
    return round(definitiva, 2)


def determinar_estado(definitiva):
    """Devuelve el estado académico según la nota definitiva."""
    if definitiva < LIMITE_HABILITA:
        return ESTADO_REPROBADO
    if definitiva < LIMITE_APROBADO:
        return ESTADO_HABILITA
    return ESTADO_APROBADO
