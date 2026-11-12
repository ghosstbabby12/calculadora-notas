"""Pruebas E2E del panel técnico (Persona C).

Comprueban las cuatro demostraciones que se usan en la sustentación:
arquitectura, contrato HTTP, batería de valores límite y laboratorio de carga.

Requisitos: docker compose up -d --wait frontend
Ejecución:  pytest -m e2e --no-cov
"""

import os

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = pytest.mark.e2e

URL_FRONTEND = os.getenv("FRONTEND_URL", "http://localhost:8080")


@pytest.fixture
def panel(page: Page) -> Page:
    """Abre el frontend y entra al panel técnico con la API confirmada."""
    page.goto(URL_FRONTEND)
    expect(page.get_by_test_id("estado-servidor")).to_have_text("Servidor en línea")
    page.get_by_test_id("pestana-tecnico").click()
    expect(page.get_by_test_id("chip-api")).to_have_text("API: en línea")
    return page


def test_arquitectura_muestra_latencia(panel: Page):
    # Arrange: el fixture ya verificó la API

    # Act
    panel.get_by_test_id("btn-verificar-arquitectura").click()

    # Assert
    expect(panel.get_by_test_id("chip-latencia")).to_contain_text("Latencia:")
    expect(panel.get_by_test_id("chip-latencia")).not_to_contain_text("—")


def test_contrato_devuelve_200_y_json(panel: Page):
    # Arrange: GET /salud viene preseleccionado

    # Act
    panel.get_by_test_id("btn-contrato").click()

    # Assert
    expect(panel.get_by_test_id("contrato-estado")).to_have_text("HTTP 200")
    expect(panel.get_by_test_id("contrato-json")).to_contain_text('"estado": "ok"')


def test_bateria_bva_cumple_los_once_casos(panel: Page):
    # Arrange
    boton = panel.get_by_test_id("btn-bva")

    # Act
    boton.click()

    # Assert
    expect(panel.get_by_test_id("bva-resumen")).to_have_text(
        "11 de 11 casos cumplen", timeout=30_000
    )
    expect(panel.get_by_test_id("tabla-bva").locator("tbody tr.fila-ok")).to_have_count(11)


def test_laboratorio_de_carga_informa_metricas(panel: Page):
    # Arrange: la duración mínima es 10 s por el muestreo de Locust
    panel.get_by_test_id("carga-usuarios").fill("5")
    panel.get_by_test_id("carga-duracion").fill("10")

    # Act
    panel.get_by_test_id("btn-carga").click()

    # Assert
    veredicto = panel.get_by_test_id("carga-veredicto")
    expect(veredicto).to_be_visible(timeout=120_000)
    expect(veredicto).to_contain_text("p95")
    expect(panel.get_by_test_id("kpi-peticiones")).not_to_have_text("—")
    expect(panel.get_by_test_id("kpi-rps")).not_to_have_text("—")
