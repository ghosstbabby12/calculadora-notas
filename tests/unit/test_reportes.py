"""Pruebas unitarias de app/reportes.py.

El cliente S3 se reemplaza por un MagicMock (doble de prueba), por lo que estas
pruebas no necesitan LocalStack ni conexión de red.
"""

import re
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.reportes import exportar_a_s3, generar_csv, generar_nombre_archivo

ENCABEZADO = "codigo,nombre,definitiva,estado\n"
PATRON_NOMBRE = re.compile(r"^reporte_notas_\d{8}_\d{6}\.csv$")


@pytest.fixture
def estudiantes():
    """Dos estudiantes de ejemplo con los campos que usa el reporte."""
    return [
        {"codigo": "A001", "nombre": "Ana", "definitiva": 4.1, "estado": "APROBADO"},
        {"codigo": "B002", "nombre": "Luis", "definitiva": 2.5, "estado": "HABILITA"},
    ]


@pytest.fixture
def cliente_s3():
    """Cliente S3 simulado."""
    return MagicMock()


# ---------------------------------------------------------------------------
# generar_csv
# ---------------------------------------------------------------------------
def test_generar_csv_incluye_encabezado_y_una_fila_por_estudiante(estudiantes):
    # Arrange
    esperado = ENCABEZADO + "A001,Ana,4.1,APROBADO\n" + "B002,Luis,2.5,HABILITA\n"

    # Act
    contenido = generar_csv(estudiantes)

    # Assert
    assert contenido == esperado


def test_generar_csv_lista_vacia_solo_devuelve_encabezado():
    # Arrange
    estudiantes = []

    # Act
    contenido = generar_csv(estudiantes)

    # Assert
    assert contenido == ENCABEZADO


def test_generar_csv_ignora_campos_adicionales():
    # Arrange
    estudiantes = [
        {
            "id": 1,
            "codigo": "C003",
            "nombre": "Eva",
            "momento1": 5.0,
            "definitiva": 1.5,
            "estado": "REPROBADO",
        }
    ]

    # Act
    contenido = generar_csv(estudiantes)

    # Assert
    assert contenido == ENCABEZADO + "C003,Eva,1.5,REPROBADO\n"


def test_generar_csv_escapa_nombres_con_comas():
    # Arrange
    estudiantes = [
        {"codigo": "D004", "nombre": "Pérez, Juan", "definitiva": 3.0, "estado": "APROBADO"}
    ]

    # Act
    contenido = generar_csv(estudiantes)

    # Assert
    assert contenido == ENCABEZADO + 'D004,"Pérez, Juan",3.0,APROBADO\n'


# ---------------------------------------------------------------------------
# generar_nombre_archivo
# ---------------------------------------------------------------------------
def test_generar_nombre_archivo_usa_formato_aaaammdd_hhmmss():
    # Arrange
    momento = datetime(2026, 11, 10, 14, 5, 9)

    # Act
    nombre = generar_nombre_archivo(momento)

    # Assert
    assert nombre == "reporte_notas_20261110_140509.csv"


def test_generar_nombre_archivo_sin_parametro_usa_fecha_actual():
    # Arrange: no se pasa momento, se usa datetime.now()

    # Act
    nombre = generar_nombre_archivo()

    # Assert
    assert PATRON_NOMBRE.match(nombre)


# ---------------------------------------------------------------------------
# exportar_a_s3
# ---------------------------------------------------------------------------
@patch("app.reportes.datetime")
def test_exportar_a_s3_sube_el_csv_con_el_nombre_esperado(mock_datetime, cliente_s3):
    # Arrange
    mock_datetime.now.return_value = datetime(2026, 1, 2, 3, 4, 5)
    contenido = ENCABEZADO + "A001,Ana,4.1,APROBADO\n"

    # Act
    nombre = exportar_a_s3(contenido, cliente_s3, "reportes-notas")

    # Assert
    assert nombre == "reporte_notas_20260102_030405.csv"
    cliente_s3.put_object.assert_called_once_with(
        Bucket="reportes-notas",
        Key="reporte_notas_20260102_030405.csv",
        Body=contenido.encode("utf-8"),
        ContentType="text/csv",
    )


def test_exportar_a_s3_devuelve_nombre_con_formato_valido(cliente_s3):
    # Arrange
    contenido = ENCABEZADO

    # Act
    nombre = exportar_a_s3(contenido, cliente_s3, "otro-bucket")

    # Assert
    assert PATRON_NOMBRE.match(nombre)
    argumentos = cliente_s3.put_object.call_args.kwargs
    assert argumentos["Bucket"] == "otro-bucket"
    assert argumentos["Key"] == nombre


def test_exportar_a_s3_propaga_errores_del_cliente(cliente_s3):
    # Arrange
    cliente_s3.put_object.side_effect = RuntimeError("S3 no disponible")

    # Act / Assert
    with pytest.raises(RuntimeError, match="S3 no disponible"):
        exportar_a_s3(ENCABEZADO, cliente_s3, "reportes-notas")
