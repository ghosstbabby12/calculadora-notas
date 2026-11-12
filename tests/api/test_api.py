import csv
import io
import os
from uuid import uuid4

import pytest
import requests
from jsonschema import validate

from infra.setup_aws import crear_cliente_s3
from tests.api import schemas


def peticion(metodo, ruta, codigo, esquema, datos=None):
    base = os.getenv("API_URL", "http://localhost:5000")
    respuesta = requests.request(metodo, base + ruta, json=datos, timeout=5)
    assert respuesta.elapsed.total_seconds() < 0.5
    assert respuesta.status_code == codigo, respuesta.text
    cuerpo = respuesta.json()
    validate(cuerpo, esquema)
    return cuerpo


@pytest.fixture
def estudiante():
    datos = {"nombre": "Ana, María", "codigo": uuid4().hex}
    creado = peticion("POST", "/estudiantes", 201, schemas.ESTUDIANTE, datos)
    assert creado == {**datos, "id": creado["id"]}
    return creado


def test_salud():
    # Arrange
    ruta = "/salud"
    # Act
    cuerpo = peticion("GET", ruta, 200, schemas.SALUD)
    # Assert
    assert cuerpo["estado"] == "ok"


@pytest.mark.parametrize("datos", [{}, {"nombre": "Ana"}, {"nombre": " ", "codigo": "1"}, []])
def test_datos_incompletos(datos):
    # Arrange
    ruta = "/estudiantes"
    # Act
    cuerpo = peticion("POST", ruta, 400, schemas.ERROR, datos)
    # Assert
    assert cuerpo["error"]


@pytest.mark.parametrize("valor", [5.1, -0.1, None, "4.0", True])
def test_notas_invalidas(estudiante, valor):
    # Arrange
    ruta = f"/estudiantes/{estudiante['id']}/notas"
    datos = dict(momento1=3, momento2=valor, momento3=3)
    # Act
    cuerpo = peticion("POST", ruta, 400, schemas.ERROR, datos)
    # Assert
    assert cuerpo["error"]


@pytest.mark.parametrize("metodo,recurso", [("GET", "promedio"), ("POST", "notas")])
def test_inexistente(metodo, recurso):
    # Arrange
    ruta = f"/estudiantes/0/{recurso}"
    # Act
    cuerpo = peticion(metodo, ruta, 404, schemas.ERROR)
    # Assert
    assert cuerpo["error"]


def test_sin_notas(estudiante):
    # Arrange
    ruta = f"/estudiantes/{estudiante['id']}/promedio"
    # Act
    cuerpo = peticion("GET", ruta, 404, schemas.ERROR)
    # Assert
    assert cuerpo["error"]


def test_flujo_hasta_csv(estudiante):
    # Arrange
    identificador = estudiante["id"]
    ruta = f"/estudiantes/{identificador}"
    datos = dict(momento1=3, momento2=3, momento3=3)
    # Act
    notas = peticion("POST", ruta + "/notas", 201, schemas.NOTAS, datos)
    promedio = peticion("GET", ruta + "/promedio", 200, schemas.PROMEDIO)
    reporte = peticion("POST", "/reportes/exportar", 201, schemas.REPORTE)
    objeto = crear_cliente_s3().get_object(Bucket=reporte["bucket"], Key=reporte["archivo"])
    filas = csv.DictReader(io.StringIO(objeto["Body"].read().decode("utf-8")))
    # Assert
    assert notas == dict(id=identificador, definitiva=3.0, estado="APROBADO")
    assert promedio == {**notas, "nombre": estudiante["nombre"]}
    assert dict(nombre=estudiante["nombre"], codigo=estudiante["codigo"],
                definitiva="3.0", estado="APROBADO") in filas
