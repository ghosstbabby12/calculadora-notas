from unittest.mock import Mock

import pytest
from botocore.exceptions import EndpointConnectionError

from app.main import crear_app


@pytest.fixture
def servicios():
    s3 = Mock()
    return crear_app(s3).test_client(), s3


def test_actualizar_y_exportar(servicios):
    # Arrange
    cliente, s3 = servicios
    estudiante = cliente.post("/estudiantes", json={"nombre": "Luis", "codigo": "A1"}).json
    ruta = f"/estudiantes/{estudiante['id']}"
    cliente.post(ruta + "/notas", json=dict(momento1=0, momento2=0, momento3=0))
    # Act
    cliente.post(ruta + "/notas", json=dict(momento1=3, momento2=4, momento3=5))
    rechazo = cliente.post(ruta + "/notas", json=dict(momento1=3, momento2=4, momento3=8))
    promedio = cliente.get(ruta + "/promedio").json
    reporte = cliente.post("/reportes/exportar")
    # Assert
    assert rechazo.status_code == 400
    assert promedio == dict(id=estudiante["id"], nombre="Luis", definitiva=4.1, estado="APROBADO")
    assert reporte.status_code == 201
    assert s3.put_object.call_args.kwargs["Body"].decode().splitlines() == [
        "codigo,nombre,definitiva,estado", "A1,Luis,4.1,APROBADO"]


def test_error_de_almacenamiento(servicios):
    # Arrange
    cliente, s3 = servicios
    s3.put_object.side_effect = EndpointConnectionError(endpoint_url="http://localstack:4566")
    # Act
    respuesta = cliente.post("/reportes/exportar")
    # Assert
    assert respuesta.status_code == 503
    assert "error" in respuesta.json
