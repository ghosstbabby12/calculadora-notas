"""Prueba de ESTRÉS: sube la carga por escalones hasta encontrar el punto de quiebre.

Diferencia con load/locustfile.py (prueba de CARGA):
- Carga:  carga fija y esperada (100 usuarios). Pregunta: ¿cumple los umbrales?
- Estrés: carga creciente más allá de lo esperado. Pregunta: ¿dónde se rompe
  y se recupera cuando la carga baja?

Reutiliza el mismo usuario (Estudiante) y los mismos umbrales que la prueba de
carga: un escalón "se rompe" si supera el 1 % de errores o un p95 de 800 ms.
Después del primer escalón roto (o del último) se baja a pocos usuarios para
comprobar la RECUPERACIÓN del servicio.

Uso (la forma de la carga la define esta clase, no se pasan -u ni -r):
    locust -f load/estres.py --host http://127.0.0.1:5055 --headless \
        --html reporte-estres.html --csv resultados_estres
"""

import csv
import logging
from dataclasses import asdict, dataclass

from locust import LoadTestShape
from locust.stats import calculate_response_time_percentile

try:  # Desde pytest (raíz del repo) y desde locust (carpeta load/ en sys.path).
    from load.locustfile import LIMITE_ERRORES, LIMITE_P95_MS, Estudiante  # noqa: F401
except ImportError:  # pragma: no cover
    from locustfile import LIMITE_ERRORES, LIMITE_P95_MS, Estudiante  # noqa: F401

LOGGER = logging.getLogger(__name__)

ESCALONES = (100, 250, 500, 1000, 1500, 2000, 3000, 4000, 5000)
DURACION_ESCALON_S = 30
# Rápido para que cada escalón pase la mayor parte del tiempo a carga plena.
USUARIOS_POR_SEGUNDO = 200
USUARIOS_RECUPERACION = 50
# La bajada a la fase de recuperación es casi instantánea.
TASA_BAJADA = 2000
ARCHIVO_RESUMEN = "resultados_estres_escalones.csv"


@dataclass(frozen=True)
class Foto:
    """Estado acumulado de las estadísticas en un instante."""

    peticiones: int
    fallos: int
    tiempo_total_ms: float
    tiempos: dict


@dataclass(frozen=True)
class Escalon:
    fase: str
    usuarios: int
    peticiones: int
    rps: float
    media_ms: float
    p95_ms: float
    fallos_pct: float
    roto: bool


def tomar_foto(total):
    """Copia los contadores acumulados del total de Locust."""
    return Foto(
        peticiones=total.num_requests,
        fallos=total.num_failures,
        tiempo_total_ms=total.total_response_time,
        tiempos=dict(total.response_times),
    )


def resumir_escalon(fase, usuarios, antes, despues, duracion_s):
    """Calcula las métricas SOLO del escalón (diferencia entre dos fotos)."""
    peticiones = despues.peticiones - antes.peticiones
    fallos = despues.fallos - antes.fallos
    tiempos = {
        ms: despues.tiempos[ms] - antes.tiempos.get(ms, 0)
        for ms in despues.tiempos
        if despues.tiempos[ms] - antes.tiempos.get(ms, 0) > 0
    }
    p95 = calculate_response_time_percentile(tiempos, sum(tiempos.values()), 0.95) if tiempos else 0
    media = (despues.tiempo_total_ms - antes.tiempo_total_ms) / peticiones if peticiones else 0.0
    ratio_fallos = fallos / peticiones if peticiones else 1.0
    return Escalon(
        fase=fase,
        usuarios=usuarios,
        peticiones=peticiones,
        rps=round(peticiones / duracion_s, 1),
        media_ms=round(media, 1),
        p95_ms=float(p95),
        fallos_pct=round(ratio_fallos * 100, 2),
        roto=ratio_fallos > LIMITE_ERRORES or p95 > LIMITE_P95_MS,
    )


def guardar_resumen(escalones, ruta=ARCHIVO_RESUMEN):
    """Escribe un CSV con una fila por escalón (para el informe)."""
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(Escalon.__dataclass_fields__))
        escritor.writeheader()
        escritor.writerows(asdict(e) for e in escalones)


class EstresEscalonado(LoadTestShape):
    """Escalones crecientes y luego una fase de recuperación con poca carga."""

    def __init__(self):
        super().__init__()
        self.resultados = []
        self.indice = 0
        self.fase = "subida"
        self.inicio_fase = 0.0
        self.foto = None

    def _usuarios_actuales(self):
        return USUARIOS_RECUPERACION if self.fase == "recuperacion" else ESCALONES[self.indice]

    def _cerrar_fase(self, ahora):
        escalon = resumir_escalon(
            self.fase,
            self._usuarios_actuales(),
            self.foto,
            tomar_foto(self.runner.stats.total),
            ahora - self.inicio_fase,
        )
        self.resultados.append(escalon)
        LOGGER.info("Escalón terminado: %s", escalon)
        return escalon

    def _siguiente_fase(self, escalon):
        """Devuelve False cuando ya no hay más fases."""
        if self.fase == "recuperacion":
            return False
        if escalon.roto or self.indice == len(ESCALONES) - 1:
            self.fase = "recuperacion"
        else:
            self.indice += 1
        return True

    def tick(self):
        ahora = self.get_run_time()
        if self.foto is None:
            self.foto = tomar_foto(self.runner.stats.total)
        if ahora - self.inicio_fase >= DURACION_ESCALON_S:
            escalon = self._cerrar_fase(ahora)
            if not self._siguiente_fase(escalon):
                guardar_resumen(self.resultados)
                return None
            self.inicio_fase = ahora
            self.foto = tomar_foto(self.runner.stats.total)
        tasa = TASA_BAJADA if self.fase == "recuperacion" else USUARIOS_POR_SEGUNDO
        return self._usuarios_actuales(), tasa
