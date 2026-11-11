"""Pruebas de servicios (API) con ``requests`` + JSON Schema.

Contrato bajo prueba:
- POST /estudiantes -> 201
- POST /estudiantes/{id}/notas -> 201 o 400 (404 si el id no existe)
- GET /estudiantes/{id}/promedio -> 200 o 404

Se ejecutan contra un servicio vivo. La URL base se toma de:
- variable de entorno API_BASE_URL (en Docker Compose es http://api:5000)
- por defecto http://localhost:5000 (corrida local)

Estrategia AAA + partición de equivalencia / BVA reutilizada de Persona A:
- fronteras 1.99 / 2.0 / 2.01 y 2.99 / 3.0 / 3.01 para el estado,
- inválidos -0.1 / 5.1 / None / "4.0" -> 400,
- inexistentes -> 404.
"""

import os

import pytest
import requests
from jsonschema import validate

from .schemas import (
    ERROR_RESPUESTA,
    ESTUDIANTE_CREACION,
    HEALTH_RESPUESTA,
    NOTAS_REGISTRO,
    PROMEDIO_RESPUESTA,
)

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")


def _esperar_api(timeout_seg=60):
    """Espera a que /health responda 200 (útil en Compose, donde api tarda)."""
    import time

    inicio = time.time()
    while time.time() - inicio < timeout_seg:
        try:
            respuesta = requests.get(f"{BASE_URL}/health", timeout=2)
            if respuesta.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    pytest.fail(f"La API no respondió en {BASE_URL}/health tras {timeout_seg}s")


@pytest.fixture(scope="session", autouse=True)
def esperar_servicio():
    _esperar_api()


def _crear_estudiante(nombre="Ana Prueba", codigo="T001"):
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes", json={"nombre": nombre, "codigo": codigo}, timeout=5
    )
    assert respuesta.status_code == 201, respuesta.text
    validate(respuesta.json(), ESTUDIANTE_CREACION)
    return respuesta.json()["id"]


# ---------------------------------------------------------------------------
# POST /estudiantes -> 201
# ---------------------------------------------------------------------------
def test_health_responde_ok():
    # Arrange: servicio levantado (fixture esperar_servicio)

    # Act
    respuesta = requests.get(f"{BASE_URL}/health", timeout=5)

    # Assert
    assert respuesta.status_code == 200
    validate(respuesta.json(), HEALTH_RESPUESTA)


def test_crear_estudiante_devuelve_201_y_contrato():
    # Arrange
    payload = {"nombre": "Luis", "codigo": "A001"}

    # Act
    respuesta = requests.post(f"{BASE_URL}/estudiantes", json=payload, timeout=5)

    # Assert
    assert respuesta.status_code == 201
    validate(respuesta.json(), ESTUDIANTE_CREACION)
    assert respuesta.json()["nombre"] == "Luis"


def test_crear_estudiante_sin_nombre_devuelve_400():
    # Arrange: falta el campo obligatorio
    payload = {"codigo": "SIN-NOMBRE"}

    # Act
    respuesta = requests.post(f"{BASE_URL}/estudiantes", json=payload, timeout=5)

    # Assert
    assert respuesta.status_code == 400
    validate(respuesta.json(), ERROR_RESPUESTA)


def test_crear_estudiante_cuerpo_no_json_devuelve_400():
    # Arrange: cuerpo que no es JSON válido

    # Act
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes", data="esto no es json", headers={"Content-Type": "application/json"}, timeout=5
    )

    # Assert
    assert respuesta.status_code == 400
    validate(respuesta.json(), ERROR_RESPUESTA)


# ---------------------------------------------------------------------------
# POST /estudiantes/{id}/notas -> 201 o 400/404
# ---------------------------------------------------------------------------
def test_registrar_notas_devuelve_201_y_estado_aprobado():
    # Arrange
    id_estudiante = _crear_estudiante()

    # Act: 3.0*0.3 + 3.0*0.3 + 3.0*0.4 = 3.0 -> APROBADO
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json={"m1": 3.0, "m2": 3.0, "m3": 3.0}, timeout=5
    )

    # Assert
    assert respuesta.status_code == 201
    validate(respuesta.json(), NOTAS_REGISTRO)
    assert respuesta.json()["definitiva"] == 3.0
    assert respuesta.json()["estado"] == "APROBADO"


@pytest.mark.parametrize(
    "m1, m2, m3, definitiva, estado",
    [
        (1.0, 2.0, 2.5, 1.9, "REPROBADO"),  # 0.3+0.6+1.0
        (2.0, 2.0, 2.0, 2.0, "HABILITA"),  # BVA frontera 2.0
        (2.01, 2.01, 2.01, 2.01, "HABILITA"),  # BVA justo encima de 2.0
        (2.99, 2.99, 2.99, 2.99, "HABILITA"),  # BVA justo debajo de 3.0
        (3.0, 3.0, 3.0, 3.0, "APROBADO"),  # BVA frontera 3.0
    ],
    ids=["reprobado-1.9", "habilita-2.0", "habilita-2.01", "habilita-2.99", "aprobado-3.0"],
)
def test_registrar_notas_fronteras_bva(m1, m2, m3, definitiva, estado):
    # Arrange
    id_estudiante = _crear_estudiante()

    # Act
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json={"m1": m1, "m2": m2, "m3": m3}, timeout=5
    )

    # Assert
    assert respuesta.status_code == 201
    validate(respuesta.json(), NOTAS_REGISTRO)
    assert respuesta.json()["definitiva"] == definitiva
    assert respuesta.json()["estado"] == estado


@pytest.mark.parametrize(
    "payload",
    [
        {"m1": -0.1, "m2": 3.0, "m3": 3.0},  # BVA bajo rango
        {"m1": 3.0, "m2": 5.1, "m3": 3.0},  # BVA sobre rango
        {"m1": None, "m2": 3.0, "m3": 3.0},  # TypeError
        {"m1": "4.0", "m2": 3.0, "m3": 3.0},  # TypeError texto
        {"m1": 3.0, "m2": 3.0},  # falta m3
        {"m1": True, "m2": 3.0, "m3": 3.0},  # bool no es nota válida
    ],
    ids=["negativa", "mayor-5", "none", "texto", "falta-m3", "booleano"],
)
def test_registrar_notas_invalidas_devuelve_400(payload):
    # Arrange
    id_estudiante = _crear_estudiante()

    # Act
    respuesta = requests.post(f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json=payload, timeout=5)

    # Assert
    assert respuesta.status_code == 400
    validate(respuesta.json(), ERROR_RESPUESTA)


def test_registrar_notas_estudiante_inexistente_devuelve_404():
    # Arrange: id que no existe

    # Act
    respuesta = requests.post(f"{BASE_URL}/estudiantes/999999/notas", json={"m1": 3, "m2": 3, "m3": 3}, timeout=5)

    # Assert
    assert respuesta.status_code == 404
    validate(respuesta.json(), ERROR_RESPUESTA)


# ---------------------------------------------------------------------------
# GET /estudiantes/{id}/promedio -> 200 o 404
# ---------------------------------------------------------------------------
def test_obtener_promedio_devuelve_200_y_contrato():
    # Arrange
    id_estudiante = _crear_estudiante()
    requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json={"m1": 4.0, "m2": 4.0, "m3": 4.0}, timeout=5
    )

    # Act
    respuesta = requests.get(f"{BASE_URL}/estudiantes/{id_estudiante}/promedio", timeout=5)

    # Assert
    assert respuesta.status_code == 200
    validate(respuesta.json(), PROMEDIO_RESPUESTA)
    assert respuesta.json()["definitiva"] == 4.0
    assert respuesta.json()["estado"] == "APROBADO"


def test_obtener_promedio_sin_notas_devuelve_404():
    # Arrange: estudiante recién creado, sin notas

    # Act
    id_estudiante = _crear_estudiante()
    respuesta = requests.get(f"{BASE_URL}/estudiantes/{id_estudiante}/promedio", timeout=5)

    # Assert
    assert respuesta.status_code == 404
    validate(respuesta.json(), ERROR_RESPUESTA)


def test_obtener_promedio_estudiante_inexistente_devuelve_404():
    # Arrange: id que no existe

    # Act
    respuesta = requests.get(f"{BASE_URL}/estudiantes/999999/promedio", timeout=5)

    # Assert
    assert respuesta.status_code == 404
    validate(respuesta.json(), ERROR_RESPUESTA)
