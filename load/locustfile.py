"""Carga sobre la publicación y consulta de calificaciones (Persona C).

Umbrales de aceptación: menos del 1 % de errores y p95 de 800 ms como máximo.
La corrida devuelve código de salida 1 cuando incumple alguno, para que el
pipeline de GitHub Actions marque el job en rojo.
"""
import logging
import random
from uuid import uuid4

import requests
from locust import HttpUser, between, events, task
from locust.exception import StopUser

LOGGER = logging.getLogger(__name__)

LIMITE_ERRORES = 0.01
LIMITE_P95_MS = 800


@events.test_start.add_listener
def verificar_api(environment, **kwargs):
    """Comprueba /salud antes de medir y falla rápido si no responde la API.

    En macOS el puerto 5000 lo puede ocupar el Receptor de AirPlay, que
    responde 403 a localhost. Sin esta comprobación la corrida gastaría un
    minuto midiendo errores ajenos al servicio.
    """
    try:
        respuesta = requests.get(f"{environment.host}/salud", timeout=5)
    except requests.RequestException as error:
        _abortar(environment, f"No se pudo conectar con {environment.host}: {error}")
        return
    if respuesta.status_code != 200:
        _abortar(
            environment,
            f"{environment.host}/salud respondió {respuesta.status_code}; "
            "revisa que el puerto apunte a la API (en macOS AirPlay usa el 5000).",
        )


def _abortar(environment, mensaje):
    """Deja el mensaje en el log, marca fallo y detiene la corrida."""
    LOGGER.error(mensaje)
    environment.process_exit_code = 1
    detener = getattr(environment.runner, "quit", None)
    if detener is not None:
        detener()


class Estudiante(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        datos = {"nombre": "Estudiante de carga", "codigo": uuid4().hex}
        respuesta = self.client.post("/estudiantes", json=datos)
        if respuesta.status_code != 201:
            raise StopUser()
        self.ruta = f"/estudiantes/{respuesta.json()['id']}"
        self.registrar_notas()

    @task(5)
    def consultar_promedio(self):
        self.client.get(self.ruta + "/promedio", name="/estudiantes/[id]/promedio")

    @task(1)
    def registrar_notas(self):
        notas = {f"momento{i}": random.randint(0, 50) / 10 for i in (1, 2, 3)}
        self.client.post(self.ruta + "/notas", json=notas, name="/estudiantes/[id]/notas")


@events.quitting.add_listener
def evaluar_carga(environment, **kwargs):
    """Marca la corrida como fallida si se superan los umbrales acordados."""
    total = environment.stats.total
    if (
        not total.num_requests
        or total.fail_ratio > LIMITE_ERRORES
        or total.get_response_time_percentile(0.95) > LIMITE_P95_MS
    ):
        environment.process_exit_code = 1
