"""Pruebas de la prueba de carga: umbrales y verificación previa (Persona C).

Locust entrega un objeto `environment` con las estadísticas acumuladas; aquí se
simula para comprobar que el pipeline falla cuando se supera el 1 % de errores
o el p95 de 800 ms, y que pasa cuando la corrida está dentro de los umbrales.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from load.locustfile import (
    LIMITE_ERRORES,
    LIMITE_P95_MS,
    evaluar_carga,
    verificar_api,
)


def entorno(num_requests=100, fail_ratio=0.0, p95_ms=100.0):
    """Simula el `environment` de Locust con un total ya calculado."""
    total = SimpleNamespace(
        num_requests=num_requests,
        fail_ratio=fail_ratio,
        get_response_time_percentile=lambda percentil: p95_ms,
    )
    return SimpleNamespace(stats=SimpleNamespace(total=total), process_exit_code=None)


# ---------------------------------------------------------------------------
# evaluar_carga — BVA alrededor de ambos umbrales
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "num_requests, fail_ratio, p95_ms",
    [(100, 0.0, 100.0), (100, LIMITE_ERRORES, LIMITE_P95_MS)],
    ids=["corrida-comoda", "justo-en-el-limite-1%-y-800ms"],
)
def test_evaluar_carga_acepta_corridas_dentro_del_umbral(num_requests, fail_ratio, p95_ms):
    # Arrange
    environment = entorno(num_requests, fail_ratio, p95_ms)

    # Act
    evaluar_carga(environment)

    # Assert
    assert environment.process_exit_code is None


@pytest.mark.parametrize(
    "num_requests, fail_ratio, p95_ms",
    [
        (100, 0.011, 100.0),
        (100, 0.0, 801.0),
        (0, 0.0, 0.0),
    ],
    ids=[
        "supera-1%-de-errores",
        "supera-p95-de-800ms",
        "sin-peticiones",
    ],
)
def test_evaluar_carga_falla_fuera_del_umbral(num_requests, fail_ratio, p95_ms):
    # Arrange
    environment = entorno(num_requests, fail_ratio, p95_ms)

    # Act
    evaluar_carga(environment)

    # Assert
    assert environment.process_exit_code == 1


# ---------------------------------------------------------------------------
# verificar_api — comprobación previa contra /salud
# ---------------------------------------------------------------------------
def _entorno_con_runner():
    environment = entorno()
    environment.host = "http://127.0.0.1:5000"
    environment.runner = Mock()
    return environment


@patch("load.locustfile.requests.get")
def test_verificar_api_continua_cuando_salud_responde_200(mock_get):
    # Arrange
    mock_get.return_value = SimpleNamespace(status_code=200)
    environment = _entorno_con_runner()

    # Act
    verificar_api(environment)

    # Assert
    assert environment.process_exit_code is None
    environment.runner.quit.assert_not_called()
    mock_get.assert_called_once_with("http://127.0.0.1:5000/salud", timeout=5)


@patch("load.locustfile.requests.get")
def test_verificar_api_aborta_cuando_el_puerto_no_es_la_api(mock_get):
    # Arrange: 403 es lo que devuelve AirPlay en macOS al ocupar el 5000
    mock_get.return_value = SimpleNamespace(status_code=403)
    environment = _entorno_con_runner()

    # Act
    verificar_api(environment)

    # Assert
    assert environment.process_exit_code == 1
    environment.runner.quit.assert_called_once()


@patch("load.locustfile.requests.get")
def test_verificar_api_aborta_cuando_no_hay_conexion(mock_get):
    # Arrange
    mock_get.side_effect = requests.ConnectionError("sin red")
    environment = _entorno_con_runner()

    # Act
    verificar_api(environment)

    # Assert
    assert environment.process_exit_code == 1
    environment.runner.quit.assert_called_once()
