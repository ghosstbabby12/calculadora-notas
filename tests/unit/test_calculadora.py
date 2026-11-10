"""Pruebas unitarias de app/calculadora.py.

PARTICIÓN DE EQUIVALENCIA — validar_nota(nota)
+------+------------------------------+-----------------------+-------------+
| Clase| Descripción                  | Ejemplo representativo| Resultado   |
+------+------------------------------+-----------------------+-------------+
| CV1  | Número en [0.0, 5.0]         | 3.5, 4 (int)          | float       |
| CI1  | Número < 0.0                 | -0.1, -3              | ValueError  |
| CI2  | Número > 5.0                 | 5.1, 10               | ValueError  |
| CI3  | None                         | None                  | TypeError   |
| CI4  | Texto (aunque parezca número)| "4.0"                 | TypeError   |
| CI5  | Booleano (bool hereda de int)| True, False           | TypeError   |
| CI6  | Colección                    | [4.0], {"n": 4}       | TypeError   |
+------+------------------------------+-----------------------+-------------+

PARTICIÓN DE EQUIVALENCIA — determinar_estado(definitiva)
+------+------------------------------+-----------------------+-------------+
| Clase| Rango                        | Ejemplo representativo| Resultado   |
+------+------------------------------+-----------------------+-------------+
| CE1  | [0.0, 2.0)                   | 1.0                   | REPROBADO   |
| CE2  | [2.0, 3.0)                   | 2.5                   | HABILITA    |
| CE3  | [3.0, 5.0]                   | 4.0                   | APROBADO    |
+------+------------------------------+-----------------------+-------------+

ANÁLISIS DE VALORES LÍMITE (BVA)
- validar_nota: -0.1 | 0.0 ... 5.0 | 5.1  (justo fuera / justo en el borde).
- determinar_estado: 1.99 | 2.0 | 2.01 y 2.99 | 3.0 | 3.01 (alrededor de cada
  frontera de estado) más los extremos absolutos 0.0 y 5.0.
  Se usa un paso de 0.01 porque la definitiva se redondea a 2 decimales:
  no existe ninguna definitiva entre 1.99 y 2.0.
"""

import pytest

from app.calculadora import calcular_definitiva, determinar_estado, validar_nota


# ---------------------------------------------------------------------------
# validar_nota — casos válidos (CV1 + BVA dentro del rango)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "nota, esperado",
    [
        (0.0, 0.0),
        (5.0, 5.0),
        (3.5, 3.5),
        (4, 4.0),
    ],
    ids=[
        "BVA-limite-inferior-0.0",
        "BVA-limite-superior-5.0",
        "CV1-valor-tipico-3.5",
        "CV1-entero-4-se-convierte-a-float",
    ],
)
def test_validar_nota_valida_devuelve_float(nota, esperado):
    # Arrange: la nota y el valor esperado llegan por parametrize

    # Act
    resultado = validar_nota(nota)

    # Assert
    assert resultado == esperado
    assert isinstance(resultado, float)


# ---------------------------------------------------------------------------
# validar_nota — fuera de rango (CI1, CI2 + BVA fuera del rango)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "nota",
    [-0.1, 5.1, -3, 10],
    ids=[
        "BVA-justo-debajo-de-0.0",
        "BVA-justo-encima-de-5.0",
        "CI1-negativo-entero",
        "CI2-mayor-que-5",
    ],
)
def test_validar_nota_fuera_de_rango_lanza_value_error(nota):
    # Arrange: la nota inválida llega por parametrize

    # Act / Assert
    with pytest.raises(ValueError, match="entre 0.0 y 5.0"):
        validar_nota(nota)


# ---------------------------------------------------------------------------
# validar_nota — tipo inválido (CI3 a CI6)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "nota",
    [None, "4.0", True, False, [4.0], {"nota": 4.0}],
    ids=[
        "CI3-None",
        "CI4-texto-numerico",
        "CI5-booleano-True",
        "CI5-booleano-False",
        "CI6-lista",
        "CI6-diccionario",
    ],
)
def test_validar_nota_tipo_invalido_lanza_type_error(nota):
    # Arrange: el valor de tipo inválido llega por parametrize

    # Act / Assert
    with pytest.raises(TypeError, match="numérica"):
        validar_nota(nota)


# ---------------------------------------------------------------------------
# calcular_definitiva — pesos y redondeo
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "m1, m2, m3, esperado",
    [
        (5.0, 0.0, 0.0, 1.5),
        (0.0, 5.0, 0.0, 1.5),
        (0.0, 0.0, 5.0, 2.0),
        (0.0, 0.0, 0.0, 0.0),
        (5.0, 5.0, 5.0, 5.0),
        (3.33, 3.33, 3.34, 3.33),
        (4.15, 3.27, 2.88, 3.38),
        (3, 4, 5, 4.1),
    ],
    ids=[
        "peso-momento1-30%",
        "peso-momento2-30%",
        "peso-momento3-40%",
        "todas-en-cero",
        "todas-en-cinco",
        "redondeo-hacia-abajo-3.334->3.33",
        "redondeo-hacia-arriba-3.378->3.38",
        "acepta-enteros",
    ],
)
def test_calcular_definitiva_aplica_pesos_y_redondea(m1, m2, m3, esperado):
    # Arrange: las tres notas y el resultado esperado llegan por parametrize

    # Act
    definitiva = calcular_definitiva(m1, m2, m3)

    # Assert
    assert definitiva == esperado


def test_calcular_definitiva_redondea_a_dos_decimales():
    # Arrange
    m1, m2, m3 = 3.33, 4.17, 2.91  # 0.999 + 1.251 + 1.164 = 3.414

    # Act
    definitiva = calcular_definitiva(m1, m2, m3)

    # Assert
    assert definitiva == round(definitiva, 2)
    assert definitiva == 3.41


@pytest.mark.parametrize(
    "m1, m2, m3, excepcion",
    [
        (5.1, 3.0, 3.0, ValueError),
        (3.0, -0.1, 3.0, ValueError),
        (3.0, 3.0, 5.1, ValueError),
        (None, 3.0, 3.0, TypeError),
        (3.0, "4.0", 3.0, TypeError),
        (3.0, 3.0, True, TypeError),
    ],
    ids=[
        "momento1-fuera-de-rango",
        "momento2-fuera-de-rango",
        "momento3-fuera-de-rango",
        "momento1-None",
        "momento2-texto",
        "momento3-booleano",
    ],
)
def test_calcular_definitiva_valida_cada_momento(m1, m2, m3, excepcion):
    # Arrange: una de las tres notas es inválida (llega por parametrize)

    # Act / Assert
    with pytest.raises(excepcion):
        calcular_definitiva(m1, m2, m3)


# ---------------------------------------------------------------------------
# determinar_estado — BVA en las fronteras + particiones
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "definitiva, estado_esperado",
    [
        (0.0, "REPROBADO"),
        (1.0, "REPROBADO"),
        (1.99, "REPROBADO"),
        (2.0, "HABILITA"),
        (2.01, "HABILITA"),
        (2.5, "HABILITA"),
        (2.99, "HABILITA"),
        (3.0, "APROBADO"),
        (3.01, "APROBADO"),
        (4.0, "APROBADO"),
        (5.0, "APROBADO"),
    ],
    ids=[
        "BVA-minimo-absoluto-0.0-REPROBADO",
        "CE1-tipico-1.0-REPROBADO",
        "BVA-justo-debajo-de-2.0-REPROBADO",
        "BVA-frontera-2.0-HABILITA",
        "BVA-justo-encima-de-2.0-HABILITA",
        "CE2-tipico-2.5-HABILITA",
        "BVA-justo-debajo-de-3.0-HABILITA",
        "BVA-frontera-3.0-APROBADO",
        "BVA-justo-encima-de-3.0-APROBADO",
        "CE3-tipico-4.0-APROBADO",
        "BVA-maximo-absoluto-5.0-APROBADO",
    ],
)
def test_determinar_estado_segun_definitiva(definitiva, estado_esperado):
    # Arrange: la definitiva y el estado esperado llegan por parametrize

    # Act
    estado = determinar_estado(definitiva)

    # Assert
    assert estado == estado_esperado


# ---------------------------------------------------------------------------
# Flujo completo: notas -> definitiva -> estado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "notas, estado_esperado",
    [
        ((1.0, 2.0, 2.5), "REPROBADO"),  # 0.3 + 0.6 + 1.0 = 1.9
        ((2.0, 2.0, 2.0), "HABILITA"),  # 2.0 exacto
        ((3.0, 3.0, 3.0), "APROBADO"),  # 3.0 exacto
    ],
    ids=["flujo-REPROBADO-1.9", "flujo-HABILITA-2.0", "flujo-APROBADO-3.0"],
)
def test_flujo_notas_a_estado(notas, estado_esperado):
    # Arrange
    m1, m2, m3 = notas

    # Act
    estado = determinar_estado(calcular_definitiva(m1, m2, m3))

    # Assert
    assert estado == estado_esperado
