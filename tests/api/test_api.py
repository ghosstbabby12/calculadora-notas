"""Pruebas de servicios (API) con ``requests`` + JSON Schema.

Contrato unificado Persona B + C:
- POST /estudiantes -> 201 (requiere nombre y codigo)
- POST /estudiantes/{id}/notas -> 201 o 400/404 (acepta m1/m2/m3 y momento1/2/3)
- GET /estudiantes/{id}/promedio -> 200 o 404 (devuelve id, nombre, definitiva, estado)
- GET /health y GET /salud -> 200
- POST /reportes/exportar -> 201 o 503 (requiere LocalStack/S3)

URL base: API_BASE_URL o API_URL (en Compose es http://api:5000),
por defecto http://localhost:5000.
"""

import csv
import io
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
    REPORTE,
    SALUD,
)

BASE_URL = os.getenv("API_BASE_URL", os.getenv("API_URL", "http://localhost:5000"))


def _esperar_api(timeout_seg=90):
    """Espera a que /salud o /health responda 200 (en Compose la API tarda)."""
    import time

    inicio = time.time()
    while time.time() - inicio < timeout_seg:
        for ruta in ("/salud", "/health"):
            try:
                respuesta = requests.get(f"{BASE_URL}{ruta}", timeout=2)
                if respuesta.status_code == 200:
                    return
            except requests.RequestException:
                pass
        time.sleep(1)
    pytest.fail(f"La API no respondió en {BASE_URL} tras {timeout_seg}s")


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
# Salud: /health (B) y /salud (C) son alias
# ---------------------------------------------------------------------------
def test_health_responde_ok():
    respuesta = requests.get(f"{BASE_URL}/health", timeout=5)
    assert respuesta.status_code == 200
    validate(respuesta.json(), HEALTH_RESPUESTA)


def test_salud_responde_ok():
    respuesta = requests.get(f"{BASE_URL}/salud", timeout=5)
    assert respuesta.status_code == 200
    validate(respuesta.json(), SALUD)


# ---------------------------------------------------------------------------
# POST /estudiantes -> 201
# ---------------------------------------------------------------------------
def test_crear_estudiante_devuelve_201_y_contrato():
    payload = {"nombre": "Luis", "codigo": "A001"}
    respuesta = requests.post(f"{BASE_URL}/estudiantes", json=payload, timeout=5)
    assert respuesta.status_code == 201
    validate(respuesta.json(), ESTUDIANTE_CREACION)
    assert respuesta.json()["nombre"] == "Luis"


@pytest.mark.parametrize(
    "payload",
    [
        {"codigo": "SIN-NOMBRE"},  # falta nombre
        {"nombre": "Ana"},  # falta codigo (obligatorio en contrato unificado)
        {"nombre": "   ", "codigo": "X"},  # nombre vacío
        {"nombre": "Ana", "codigo": "   "},  # codigo vacío
        {"nombre": 123, "codigo": "X"},  # tipo inválido
    ],
    ids=["sin-nombre", "sin-codigo", "nombre-vacio", "codigo-vacio", "nombre-no-texto"],
)
def test_crear_estudiante_invalido_devuelve_400(payload):
    respuesta = requests.post(f"{BASE_URL}/estudiantes", json=payload, timeout=5)
    assert respuesta.status_code == 400
    validate(respuesta.json(), ERROR_RESPUESTA)


def test_crear_estudiante_cuerpo_no_json_devuelve_400():
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes", data="esto no es json", headers={"Content-Type": "application/json"}, timeout=5
    )
    assert respuesta.status_code == 400
    validate(respuesta.json(), ERROR_RESPUESTA)


# ---------------------------------------------------------------------------
# POST /estudiantes/{id}/notas -> 201 o 400/404
# ---------------------------------------------------------------------------
def test_registrar_notas_devuelve_201_y_estado_aprobado():
    id_estudiante = _crear_estudiante()
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json={"m1": 3.0, "m2": 3.0, "m3": 3.0}, timeout=5
    )
    assert respuesta.status_code == 201
    validate(respuesta.json(), NOTAS_REGISTRO)
    assert respuesta.json()["definitiva"] == 3.0
    assert respuesta.json()["estado"] == "APROBADO"


def test_registrar_notas_acepta_alias_momento():
    # Alias de Persona C: momento1/2/3 equivale a m1/m2/m3.
    id_estudiante = _crear_estudiante()
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas",
        json={"momento1": 3, "momento2": 4, "momento3": 5},
        timeout=5,
    )
    assert respuesta.status_code == 201
    # 3*0.3 + 4*0.3 + 5*0.4 = 4.1
    assert respuesta.json()["definitiva"] == 4.1
    assert respuesta.json()["estado"] == "APROBADO"


@pytest.mark.parametrize(
    "m1, m2, m3, definitiva, estado",
    [
        (1.0, 2.0, 2.5, 1.9, "REPROBADO"),
        (2.0, 2.0, 2.0, 2.0, "HABILITA"),
        (2.01, 2.01, 2.01, 2.01, "HABILITA"),
        (2.99, 2.99, 2.99, 2.99, "HABILITA"),
        (3.0, 3.0, 3.0, 3.0, "APROBADO"),
    ],
    ids=["reprobado-1.9", "habilita-2.0", "habilita-2.01", "habilita-2.99", "aprobado-3.0"],
)
def test_registrar_notas_fronteras_bva(m1, m2, m3, definitiva, estado):
    id_estudiante = _crear_estudiante()
    respuesta = requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json={"m1": m1, "m2": m2, "m3": m3}, timeout=5
    )
    assert respuesta.status_code == 201
    validate(respuesta.json(), NOTAS_REGISTRO)
    assert respuesta.json()["definitiva"] == definitiva
    assert respuesta.json()["estado"] == estado


@pytest.mark.parametrize(
    "payload",
    [
        {"m1": -0.1, "m2": 3.0, "m3": 3.0},
        {"m1": 3.0, "m2": 5.1, "m3": 3.0},
        {"m1": None, "m2": 3.0, "m3": 3.0},
        {"m1": "4.0", "m2": 3.0, "m3": 3.0},
        {"m1": 3.0, "m2": 3.0},
        {"m1": True, "m2": 3.0, "m3": 3.0},
        {"momento1": 3, "momento2": -0.1, "momento3": 3},
        {"momento1": 3, "momento2": "4.0", "momento3": 3},
    ],
    ids=["negativa", "mayor-5", "none", "texto", "falta-m3", "booleano", "momento-negativo", "momento-texto"],
)
def test_registrar_notas_invalidas_devuelve_400(payload):
    id_estudiante = _crear_estudiante()
    respuesta = requests.post(f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json=payload, timeout=5)
    assert respuesta.status_code == 400
    validate(respuesta.json(), ERROR_RESPUESTA)


def test_registrar_notas_estudiante_inexistente_devuelve_404():
    respuesta = requests.post(f"{BASE_URL}/estudiantes/999999/notas", json={"m1": 3, "m2": 3, "m3": 3}, timeout=5)
    assert respuesta.status_code == 404
    validate(respuesta.json(), ERROR_RESPUESTA)


# ---------------------------------------------------------------------------
# GET /estudiantes/{id}/promedio -> 200 o 404
# ---------------------------------------------------------------------------
def test_obtener_promedio_devuelve_200_y_contrato():
    id_estudiante = _crear_estudiante(nombre="Eva", codigo="E001")
    requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas", json={"m1": 4.0, "m2": 4.0, "m3": 4.0}, timeout=5
    )
    respuesta = requests.get(f"{BASE_URL}/estudiantes/{id_estudiante}/promedio", timeout=5)
    assert respuesta.status_code == 200
    validate(respuesta.json(), PROMEDIO_RESPUESTA)
    assert respuesta.json()["definitiva"] == 4.0
    assert respuesta.json()["estado"] == "APROBADO"


def test_obtener_promedio_sin_notas_devuelve_404():
    id_estudiante = _crear_estudiante()
    respuesta = requests.get(f"{BASE_URL}/estudiantes/{id_estudiante}/promedio", timeout=5)
    assert respuesta.status_code == 404
    validate(respuesta.json(), ERROR_RESPUESTA)


def test_obtener_promedio_estudiante_inexistente_devuelve_404():
    respuesta = requests.get(f"{BASE_URL}/estudiantes/999999/promedio", timeout=5)
    assert respuesta.status_code == 404
    validate(respuesta.json(), ERROR_RESPUESTA)


# ---------------------------------------------------------------------------
# POST /reportes/exportar -> 201 o 503 (requiere LocalStack)
# ---------------------------------------------------------------------------
def test_exportar_reporte_y_verificar_csv_en_s3():
    import boto3

    id_estudiante = _crear_estudiante(nombre="Luis", codigo="A1")
    requests.post(
        f"{BASE_URL}/estudiantes/{id_estudiante}/notas",
        json={"momento1": 3, "momento2": 4, "momento3": 5},
        timeout=5,
    )
    respuesta = requests.post(f"{BASE_URL}/reportes/exportar", timeout=10)
    if respuesta.status_code == 503:
        pytest.skip("S3/LocalStack no disponible en este entorno")
    assert respuesta.status_code == 201
    validate(respuesta.json(), REPORTE)
    cliente_s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )
    objeto = cliente_s3.get_object(Bucket=respuesta.json()["bucket"], Key=respuesta.json()["archivo"])
    filas = list(csv.DictReader(io.StringIO(objeto["Body"].read().decode("utf-8"))))
    assert {"codigo": "A1", "nombre": "Luis", "definitiva": "4.1", "estado": "APROBADO"} in filas
