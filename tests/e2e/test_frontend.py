"""Pruebas E2E del frontend con Playwright (cima de la pirámide de pruebas).

Recorren la aplicación completa como lo haría un usuario:
navegador -> Nginx (frontend) -> proxy /api -> Flask -> calculadora.

Requisitos: docker compose up -d --wait frontend
Ejecución:  pytest -m e2e --no-cov
"""

import os
import re
from uuid import uuid4

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = pytest.mark.e2e

URL_FRONTEND = os.getenv("FRONTEND_URL", "http://localhost:8080")


# ---------------------------------------------------------------------------
# Fixtures y pasos reutilizables (DRY)
# ---------------------------------------------------------------------------
@pytest.fixture
def pagina(page: Page) -> Page:
    """Abre el frontend y espera a que el indicador confirme que la API responde."""
    page.goto(URL_FRONTEND)
    expect(page.get_by_test_id("estado-servidor")).to_have_text("Servidor en línea")
    return page


def registrar_estudiante(pagina: Page, nombre: str = "Ana Pérez") -> str:
    """Crea un estudiante con código único y devuelve el id que asignó la API."""
    pagina.get_by_label("Nombre").fill(nombre)
    pagina.get_by_label("Código").fill(uuid4().hex[:8])
    pagina.get_by_test_id("btn-crear-estudiante").click()
    id_creado = pagina.get_by_test_id("id-creado")
    expect(id_creado).to_have_text(re.compile(r"^\d+$"))
    return id_creado.text_content()


def registrar_notas(pagina: Page, id_estudiante: str, m1: float, m2: float, m3: float):
    pagina.get_by_test_id("select-estudiante").select_option(id_estudiante)
    pagina.get_by_test_id("input-momento1").fill(str(m1))
    pagina.get_by_test_id("input-momento2").fill(str(m2))
    pagina.get_by_test_id("input-momento3").fill(str(m3))
    pagina.get_by_test_id("btn-registrar-notas").click()


def consultar(pagina: Page, id_estudiante: str):
    pagina.get_by_test_id("input-id-consulta").fill(id_estudiante)
    pagina.get_by_test_id("btn-consultar").click()


# ---------------------------------------------------------------------------
# Flujo feliz
# ---------------------------------------------------------------------------
def test_flujo_completo_estudiante_aprobado(pagina: Page):
    # Arrange
    id_estudiante = registrar_estudiante(pagina, "Laura Gómez")
    registrar_notas(pagina, id_estudiante, 3.0, 3.0, 3.0)
    expect(pagina.get_by_test_id("mensaje-notas")).to_contain_text("Notas registradas")

    # Act
    consultar(pagina, id_estudiante)

    # Assert
    expect(pagina.get_by_test_id("resultado-nombre")).to_contain_text("Laura Gómez")
    expect(pagina.get_by_test_id("resultado-definitiva")).to_have_text("3.00")
    expect(pagina.get_by_test_id("resultado-estado")).to_contain_text("APROBADO")
    expect(pagina.get_by_test_id("resultado")).to_have_class(re.compile("resultado--aprobado"))


# ---------------------------------------------------------------------------
# Valores límite a través de la interfaz
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "m1, m2, m3, definitiva, estado",
    [
        (1.6, 1.7, 5.0, "2.99", "HABILITA"),  # 0.48 + 0.51 + 2.00
        (3.0, 3.1, 0.4, "1.99", "REPROBADO"),  # 0.90 + 0.93 + 0.16
    ],
    ids=["BVA-2.99-justo-debajo-de-aprobar-HABILITA", "BVA-1.99-justo-debajo-de-habilitar-REPROBADO"],
)
def test_valores_limite_muestran_estado_correcto(pagina: Page, m1, m2, m3, definitiva, estado):
    # Arrange
    id_estudiante = registrar_estudiante(pagina)
    registrar_notas(pagina, id_estudiante, m1, m2, m3)
    expect(pagina.get_by_test_id("mensaje-notas")).to_contain_text("Notas registradas")

    # Act
    consultar(pagina, id_estudiante)

    # Assert
    expect(pagina.get_by_test_id("resultado-definitiva")).to_have_text(definitiva)
    expect(pagina.get_by_test_id("resultado-estado")).to_contain_text(estado)


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------
def test_nota_fuera_de_rango_muestra_error_de_la_api(pagina: Page):
    # Arrange
    id_estudiante = registrar_estudiante(pagina)

    # Act
    registrar_notas(pagina, id_estudiante, 5.1, 3.0, 3.0)

    # Assert: marca visual del navegador + mensaje que devuelve el backend (400)
    expect(pagina.get_by_test_id("input-momento1")).to_have_attribute("aria-invalid", "true")
    mensaje = pagina.get_by_test_id("mensaje-notas")
    expect(mensaje).to_contain_text("Datos inválidos")
    expect(mensaje).to_contain_text("entre 0.0 y 5.0")


def test_consultar_id_inexistente_muestra_no_encontrado(pagina: Page):
    # Arrange
    id_inexistente = "999999"

    # Act
    consultar(pagina, id_inexistente)

    # Assert
    expect(pagina.get_by_test_id("mensaje-consulta")).to_contain_text("No encontrado")
    expect(pagina.get_by_test_id("resultado")).to_be_hidden()
