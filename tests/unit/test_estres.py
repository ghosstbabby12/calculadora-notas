"""Pruebas de la lógica de la prueba de estrés (load/estres.py).

No levantan Locust: se simulan las "fotos" de las estadísticas para verificar
que cada escalón se mide por separado y que se marca como roto con los mismos
umbrales de la prueba de carga (1 % de errores, p95 de 800 ms).
"""

import csv
from types import SimpleNamespace

import pytest

from load.estres import (
    ESCALONES,
    USUARIOS_RECUPERACION,
    EstresEscalonado,
    Foto,
    guardar_resumen,
    resumir_escalon,
    tomar_foto,
)

INICIO = Foto(peticiones=1000, fallos=0, tiempo_total_ms=10_000.0, tiempos={10: 1000})


def foto_despues(peticiones, fallos, tiempos):
    """Foto final = INICIO + lo ocurrido durante el escalón."""
    acumulados = dict(INICIO.tiempos)
    for ms, cantidad in tiempos.items():
        acumulados[ms] = acumulados.get(ms, 0) + cantidad
    tiempo_total = INICIO.tiempo_total_ms + sum(ms * n for ms, n in tiempos.items())
    return Foto(INICIO.peticiones + peticiones, INICIO.fallos + fallos, tiempo_total, acumulados)


# ---------------------------------------------------------------------------
# resumir_escalon — BVA alrededor de los umbrales
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fallos, tiempos, roto",
    [
        (0, {20: 1000}, False),
        (10, {20: 1000}, False),
        (11, {20: 1000}, True),
        (0, {20: 950, 800: 50}, False),
        (0, {20: 900, 900: 100}, True),
    ],
    ids=[
        "comodo",
        "BVA-1%-exacto-no-se-rompe",
        "BVA-1.1%-se-rompe",
        "BVA-p95-800ms-no-se-rompe",
        "p95-900ms-se-rompe",
    ],
)
def test_resumir_escalon_detecta_quiebre(fallos, tiempos, roto):
    # Arrange
    despues = foto_despues(1000, fallos, tiempos)

    # Act
    escalon = resumir_escalon("subida", 400, INICIO, despues, 10)

    # Assert
    assert escalon.roto is roto


def test_resumir_escalon_mide_solo_lo_ocurrido_en_el_escalon():
    # Arrange: el acumulado previo tiene 1000 peticiones de 10 ms
    despues = foto_despues(500, 5, {40: 500})

    # Act
    escalon = resumir_escalon("subida", 200, INICIO, despues, 10)

    # Assert
    assert (escalon.peticiones, escalon.rps) == (500, 50.0)
    assert (escalon.media_ms, escalon.p95_ms) == (40.0, 40.0)
    assert escalon.fallos_pct == 1.0


def test_resumir_escalon_sin_peticiones_cuenta_como_roto():
    # Arrange: el servidor no atendió nada durante el escalón
    despues = INICIO

    # Act
    escalon = resumir_escalon("subida", 800, INICIO, despues, 10)

    # Assert
    assert escalon.peticiones == 0
    assert escalon.roto is True


# ---------------------------------------------------------------------------
# tomar_foto y guardar_resumen
# ---------------------------------------------------------------------------
def test_tomar_foto_copia_los_tiempos():
    # Arrange
    total = SimpleNamespace(num_requests=3, num_failures=1, total_response_time=30.0, response_times={10: 3})

    # Act
    foto = tomar_foto(total)
    total.response_times[10] = 99

    # Assert: la foto no cambia aunque Locust siga sumando
    assert foto == Foto(3, 1, 30.0, {10: 3})


def test_guardar_resumen_escribe_una_fila_por_escalon(tmp_path):
    # Arrange
    escalones = [resumir_escalon("subida", u, INICIO, foto_despues(100, 0, {10: 100}), 10) for u in (100, 200)]
    ruta = tmp_path / "escalones.csv"

    # Act
    guardar_resumen(escalones, ruta)

    # Assert
    with open(ruta, encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    assert [fila["usuarios"] for fila in filas] == ["100", "200"]


# ---------------------------------------------------------------------------
# EstresEscalonado — avance de fases
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "indice, roto, fase_esperada, indice_esperado",
    [
        (0, False, "subida", 1),
        (2, True, "recuperacion", 2),
        (len(ESCALONES) - 1, False, "recuperacion", len(ESCALONES) - 1),
    ],
    ids=["sigue-subiendo", "se-rompe-y-pasa-a-recuperacion", "ultimo-escalon-pasa-a-recuperacion"],
)
def test_siguiente_fase(indice, roto, fase_esperada, indice_esperado):
    # Arrange
    forma = EstresEscalonado()
    forma.indice = indice

    # Act
    continua = forma._siguiente_fase(SimpleNamespace(roto=roto))

    # Assert
    assert continua is True
    assert (forma.fase, forma.indice) == (fase_esperada, indice_esperado)


def test_recuperacion_es_la_ultima_fase():
    # Arrange
    forma = EstresEscalonado()
    forma.fase = "recuperacion"

    # Act
    continua = forma._siguiente_fase(SimpleNamespace(roto=False))

    # Assert
    assert continua is False
    assert forma._usuarios_actuales() == USUARIOS_RECUPERACION
