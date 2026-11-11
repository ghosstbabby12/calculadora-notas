"""Pruebas unitarias de app/main.py con Flask test_client (sin red ni Docker).

Cubre el contrato unificado B + C para que el gate de cobertura (>=80 %)
siga pasando sin levantar el servicio ni LocalStack (S3 se simula con Mock).
"""

from unittest.mock import Mock

import pytest
from botocore.exceptions import EndpointConnectionError

from app.main import crear_app, reset_store


@pytest.fixture
def client():
    reset_store()
    app = crear_app(Mock())
    app.config.update({"TESTING": True})
    with app.test_client() as c:
        yield c
    reset_store()


@pytest.fixture
def servicios():
    s3 = Mock()
    reset_store()
    app = crear_app(s3)
    app.config.update({"TESTING": True})
    with app.test_client() as c:
        yield c, s3
    reset_store()


def _crear(client, nombre="Ana", codigo="A001"):
    respuesta = client.post("/estudiantes", json={"nombre": nombre, "codigo": codigo})
    assert respuesta.status_code == 201
    return respuesta.get_json()["id"]


def test_health_ok(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"status": "ok"}


def test_salud_ok(client):
    respuesta = client.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"estado": "ok"}


def test_crear_estudiante_ok(client):
    respuesta = client.post("/estudiantes", json={"nombre": "Luis", "codigo": "A001"})
    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    assert datos["id"] >= 1
    assert datos == {"id": datos["id"], "nombre": "Luis", "codigo": "A001"}


@pytest.mark.parametrize(
    "payload",
    [
        {"codigo": "X"},  # falta nombre
        {"nombre": "Ana"},  # falta codigo
        {"nombre": "   ", "codigo": "X"},  # nombre vacío
        {"nombre": "Ana", "codigo": "  "},  # codigo vacío
        {"nombre": 123, "codigo": "X"},  # tipo inválido
        {},
        [],
    ],
    ids=["sin-nombre", "sin-codigo", "nombre-vacio", "codigo-vacio", "nombre-no-texto", "vacio", "lista"],
)
def test_crear_invalido_400(client, payload):
    assert client.post("/estudiantes", json=payload).status_code == 400


def test_crear_cuerpo_no_json_400(client):
    respuesta = client.post("/estudiantes", data="no-json", content_type="application/json")
    assert respuesta.status_code == 400


def test_registrar_notas_y_promedio_aprobado(client):
    id_est = _crear(client)
    respuesta = client.post(f"/estudiantes/{id_est}/notas", json={"m1": 3, "m2": 3, "m3": 3})
    assert respuesta.status_code == 201
    assert respuesta.get_json() == {"id": id_est, "definitiva": 3.0, "estado": "APROBADO"}

    respuesta = client.get(f"/estudiantes/{id_est}/promedio")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": id_est, "nombre": "Ana", "definitiva": 3.0, "estado": "APROBADO"}


@pytest.mark.parametrize(
    "notas, definitiva, estado",
    [((1.0, 2.0, 2.5), 1.9, "REPROBADO"), ((2.0, 2.0, 2.0), 2.0, "HABILITA"), ((5, 5, 5), 5.0, "APROBADO")],
)
def test_registrar_notas_calcula_correcto(client, notas, definitiva, estado):
    id_est = _crear(client)
    m1, m2, m3 = notas
    respuesta = client.post(f"/estudiantes/{id_est}/notas", json={"m1": m1, "m2": m2, "m3": m3})
    assert respuesta.status_code == 201
    assert respuesta.get_json()["definitiva"] == definitiva
    assert respuesta.get_json()["estado"] == estado


def test_registrar_notas_alias_momento(client):
    id_est = _crear(client)
    respuesta = client.post(
        f"/estudiantes/{id_est}/notas", json={"momento1": 3, "momento2": 4, "momento3": 5}
    )
    assert respuesta.status_code == 201
    assert respuesta.get_json()["definitiva"] == 4.1


def test_nota_invalida_conserva_anteriores(servicios):
    cliente, _ = servicios
    id_est = _crear(cliente, nombre="Luis", codigo="A1")
    ruta = f"/estudiantes/{id_est}"
    cliente.post(ruta + "/notas", json={"momento1": 3, "momento2": 4, "momento3": 5})
    rechazo = cliente.post(ruta + "/notas", json={"momento1": 3, "momento2": 4, "momento3": 8})
    promedio = cliente.get(ruta + "/promedio").get_json()
    assert rechazo.status_code == 400
    assert promedio == {"id": id_est, "nombre": "Luis", "definitiva": 4.1, "estado": "APROBADO"}


@pytest.mark.parametrize(
    "payload",
    [
        {"m1": -0.1, "m2": 3, "m3": 3},
        {"m1": 5.1, "m2": 3, "m3": 3},
        {"m1": None, "m2": 3, "m3": 3},
        {"momento1": 3, "momento2": "4.0", "momento3": 3},
    ],
)
def test_registrar_notas_invalidas_400(client, payload):
    id_est = _crear(client)
    assert client.post(f"/estudiantes/{id_est}/notas", json=payload).status_code == 400


def test_registrar_notas_incompletas_400(client):
    id_est = _crear(client)
    assert client.post(f"/estudiantes/{id_est}/notas", json={"m1": 3, "m2": 3}).status_code == 400


def test_registrar_notas_sin_json_400(client):
    id_est = _crear(client)
    assert client.post(f"/estudiantes/{id_est}/notas", data="x", content_type="application/json").status_code == 400


def test_notas_estudiante_inexistente_404(client):
    assert client.post("/estudiantes/999/notas", json={"m1": 3, "m2": 3, "m3": 3}).status_code == 404


def test_promedio_sin_notas_404(client):
    id_est = _crear(client)
    assert client.get(f"/estudiantes/{id_est}/promedio").status_code == 404


def test_promedio_inexistente_404(client):
    assert client.get("/estudiantes/999/promedio").status_code == 404


def test_exportar_csv_a_s3(servicios):
    cliente, s3 = servicios
    id_est = _crear(cliente, nombre="Luis", codigo="A1")
    cliente.post(f"/estudiantes/{id_est}/notas", json={"momento1": 3, "momento2": 4, "momento3": 5})
    respuesta = cliente.post("/reportes/exportar")
    assert respuesta.status_code == 201
    assert respuesta.get_json()["bucket"]
    assert s3.put_object.call_args.kwargs["Body"].decode().splitlines() == [
        "codigo,nombre,definitiva,estado",
        "A1,Luis,4.1,APROBADO",
    ]


def test_exportar_sin_s3_devuelve_503():
    s3 = Mock()
    s3.put_object.side_effect = EndpointConnectionError(endpoint_url="http://localstack:4566")
    reset_store()
    app = crear_app(s3)
    app.config.update({"TESTING": True})
    with app.test_client() as cliente:
        respuesta = cliente.post("/reportes/exportar")
        assert respuesta.status_code == 503
        assert "error" in respuesta.get_json()
    reset_store()
