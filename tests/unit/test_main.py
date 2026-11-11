"""Pruebas unitarias de app/main.py con Flask test_client (sin red ni Docker).

Cubre la misma API que tests/api/ pero en proceso, para que el gate de
cobertura (>=80 %) siga pasando sin levantar el servicio.
"""

import pytest

from app.main import create_app, reset_store


@pytest.fixture
def client():
    reset_store()
    app = create_app()
    app.config.update({"TESTING": True})
    with app.test_client() as c:
        yield c
    reset_store()


def _crear(client, nombre="Ana", codigo="A001"):
    respuesta = client.post("/estudiantes", json={"nombre": nombre, "codigo": codigo})
    assert respuesta.status_code == 201
    return respuesta.get_json()["id"]


def test_health_ok(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"status": "ok"}


def test_crear_estudiante_ok(client):
    respuesta = client.post("/estudiantes", json={"nombre": "Luis", "codigo": "A001"})
    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    assert datos["id"] >= 1
    assert datos["nombre"] == "Luis"


def test_crear_sin_nombre_400(client):
    assert client.post("/estudiantes", json={"codigo": "X"}).status_code == 400


def test_crear_nombre_vacio_400(client):
    assert client.post("/estudiantes", json={"nombre": "   "}).status_code == 400


def test_crear_codigo_no_texto_400(client):
    assert client.post("/estudiantes", json={"nombre": "Ana", "codigo": 123}).status_code == 400


def test_crear_cuerpo_no_json_400(client):
    respuesta = client.post("/estudiantes", data="no-json", content_type="application/json")
    assert respuesta.status_code == 400


def test_registrar_notas_y_promedio_aprobado(client):
    id_est = _crear(client)
    respuesta = client.post(f"/estudiantes/{id_est}/notas", json={"m1": 3, "m2": 3, "m3": 3})
    assert respuesta.status_code == 201
    assert respuesta.get_json()["estado"] == "APROBADO"

    respuesta = client.get(f"/estudiantes/{id_est}/promedio")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["definitiva"] == 3.0


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
        f"/estudiantes/{id_est}/notas", json={"momento1": 3, "momento2": 3, "momento3": 3}
    )
    assert respuesta.status_code == 201


@pytest.mark.parametrize(
    "payload",
    [{"m1": -0.1, "m2": 3, "m3": 3}, {"m1": 5.1, "m2": 3, "m3": 3}, {"m1": None, "m2": 3, "m3": 3}],
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
