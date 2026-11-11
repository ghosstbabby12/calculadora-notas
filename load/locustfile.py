"""Carga sobre la publicación y consulta de calificaciones."""
import random
from uuid import uuid4

from locust import HttpUser, between, events, task
from locust.exception import StopUser


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
    total = environment.stats.total
    if not total.num_requests or total.fail_ratio > 0.01 or total.get_response_time_percentile(0.95) > 800:
        environment.process_exit_code = 1
