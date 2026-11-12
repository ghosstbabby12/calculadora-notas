"""Ejecutor de pruebas de carga para el panel técnico del frontend.

El panel pide una corrida, este servicio lanza Locust en un subproceso contra
el servicio `api` de Docker Compose y devuelve las métricas que Locust dejó en
sus CSV. Igual que el pipeline, la corrida falla si supera el 1 % de errores o
el p95 de 800 ms.

Solo se permite una corrida a la vez: dos pruebas simultáneas competirían por
la misma CPU y las métricas dejarían de ser comparables.
"""

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

API_INTERNA = os.getenv("API_INTERNA", "http://api:5000")
ARCHIVO_LOCUST = Path(__file__).with_name("locustfile.py")
ARCHIVO_EJECUTOR = Path(__file__).with_name("ejecutar_locust.py")

USUARIOS_MINIMO = 5
USUARIOS_MAXIMO = 200
DURACION_MINIMA = 10
DURACION_MAXIMA = 60

LIMITE_ERRORES = 0.01
LIMITE_P95_MS = 800

# Estado compartido entre la petición que arranca y las que consultan avance.
_estado = {
    "estado": "inactivo",  # inactivo | ejecutando | terminado | error
    "usuarios": 0,
    "duracion": 0,
    "inicio": None,
    "fin": None,
    "resultado": None,
    "error": None,
}
_candado = threading.Lock()


def _estado_copiado():
    """Copia el estado y calcula el avance para no exponer el diccionario vivo."""
    with _candado:
        copia = dict(_estado)
    if copia["estado"] == "ejecutando" and copia["inicio"] is not None:
        copia["transcurrido"] = round(time.time() - copia["inicio"], 1)
    elif copia["inicio"] is not None and copia["fin"] is not None:
        copia["transcurrido"] = round(copia["fin"] - copia["inicio"], 1)
    else:
        copia["transcurrido"] = 0
    copia.pop("inicio", None)
    copia.pop("fin", None)
    return copia


def _numero(fila, columna):
    """Convierte una celda del CSV de Locust en float, tolerando vacíos."""
    try:
        return float(fila.get(columna, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _leer_stats(prefijo):
    """Lee el CSV de Locust y separa el agregado de cada endpoint."""
    with open(f"{prefijo}_stats.csv", newline="", encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    agregado = next((f for f in filas if f["Name"] == "Aggregated"), None)
    if agregado is None:
        raise ValueError("Locust no dejó la fila Aggregated en el CSV")
    endpoints = [
        {
            "metodo": f["Type"],
            "ruta": f["Name"],
            "peticiones": int(_numero(f, "Request Count")),
            "fallos": int(_numero(f, "Failure Count")),
            "media_ms": round(_numero(f, "Average Response Time"), 1),
            "p95_ms": round(_numero(f, "95%"), 1),
            "max_ms": round(_numero(f, "Max Response Time"), 1),
        }
        for f in filas
        if f["Name"] != "Aggregated"
    ]
    return agregado, endpoints


def _instante(texto):
    """Interpreta el Timestamp de Locust, que puede ser epoch o ISO 8601."""
    try:
        return float(texto)
    except ValueError:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp()


def _leer_serie(prefijo):
    """Extrae la evolución por segundo de RPS y p95 para el gráfico."""
    ruta = f"{prefijo}_stats_history.csv"
    if not Path(ruta).exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as archivo:
        filas = [
            f
            for f in csv.DictReader(archivo)
            if f["Name"] == "Aggregated" and not f["Type"]
        ]
    if not filas:
        return []
    inicio = _instante(filas[0]["Timestamp"])
    serie = []
    total_anterior = None
    instante_anterior = 0.0
    for fila in filas:
        instante = round(_instante(fila["Timestamp"]) - inicio, 1)
        total = int(_numero(fila, "Total Request Count"))
        # Locust publica el total acumulado; el RPS instantáneo es su delta.
        if total_anterior is None:
            rps = 0.0
        else:
            ventana = max(0.001, instante - instante_anterior)
            rps = round((total - total_anterior) / ventana, 2)
        serie.append(
            {
                "t": instante,
                "usuarios": int(_numero(fila, "User Count")),
                "rps": rps,
                "p95_ms": round(_numero(fila, "95%"), 1),
            }
        )
        total_anterior = total
        instante_anterior = instante
    # El gráfico se dibuja en ~500 px: más de 60 puntos no aporta nada.
    paso = max(1, len(serie) // 60)
    muestras = serie[::paso]
    if muestras[-1] is not serie[-1]:
        muestras.append(serie[-1])
    return muestras


def _armar_resultado(prefijo, codigo_salida, usuarios, duracion):
    """Traduce los CSV de Locust al JSON que consume el panel."""
    agregado, endpoints = _leer_stats(prefijo)
    peticiones = int(_numero(agregado, "Request Count"))
    fallos = int(_numero(agregado, "Failure Count"))
    p95 = round(_numero(agregado, "95%"), 1)
    proporcion_fallos = fallos / peticiones if peticiones else 1.0
    return {
        "usuarios": usuarios,
        "duracion": duracion,
        "peticiones": peticiones,
        "fallos": fallos,
        "proporcion_fallos": round(proporcion_fallos, 4),
        "rps": round(_numero(agregado, "Requests/s"), 2),
        "media_ms": round(_numero(agregado, "Average Response Time"), 1),
        "p95_ms": p95,
        "max_ms": round(_numero(agregado, "Max Response Time"), 1),
        "endpoints": endpoints,
        "serie": _leer_serie(prefijo),
        "codigo_salida": codigo_salida,
        "umbrales": {"errores": LIMITE_ERRORES, "p95_ms": LIMITE_P95_MS},
        "cumple": peticiones > 0 and proporcion_fallos <= LIMITE_ERRORES and p95 <= LIMITE_P95_MS,
    }


def _correr(usuarios, duracion):
    """Ejecuta Locust y publica el resultado. Corre en un hilo aparte."""
    carpeta = tempfile.mkdtemp(prefix="locust-panel-")
    prefijo = os.path.join(carpeta, "resultado")
    comando = [
        sys.executable,
        str(ARCHIVO_EJECUTOR),
        "-f",
        str(ARCHIVO_LOCUST),
        "--host",
        API_INTERNA,
        "--headless",
        "-u",
        str(usuarios),
        "-r",
        str(max(1, usuarios // 5)),
        "-t",
        f"{duracion}s",
        "--exit-code-on-error",
        "0",
        "--csv",
        prefijo,
        "--loglevel",
        "WARNING",
    ]
    try:
        proceso = subprocess.run(
            comando, capture_output=True, text=True, timeout=duracion + 120, check=False
        )
        resultado = _armar_resultado(prefijo, proceso.returncode, usuarios, duracion)
        with _candado:
            _estado.update(estado="terminado", fin=time.time(), resultado=resultado)
    except (subprocess.SubprocessError, OSError, ValueError) as error:
        detalle = getattr(error, "stderr", None) or str(error)
        with _candado:
            _estado.update(estado="error", fin=time.time(), error=str(detalle)[-800:])
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


def _entero_positivo(datos, campo):
    """Lee un entero del JSON y lanza ValueError si no sirve."""
    valor = datos.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"El campo '{campo}' debe ser numérico")
    return int(valor)


@app.get("/salud")
def salud():
    return jsonify(estado="ok")


@app.post("/ejecutar")
def ejecutar():
    datos = request.get_json(silent=True) or {}
    try:
        usuarios = _entero_positivo(datos, "usuarios")
        duracion = _entero_positivo(datos, "duracion")
    except ValueError as error:
        return jsonify(error=str(error)), 400
    if not USUARIOS_MINIMO <= usuarios <= USUARIOS_MAXIMO:
        return jsonify(error=f"Usuarios debe estar entre {USUARIOS_MINIMO} y {USUARIOS_MAXIMO}"), 400
    if not DURACION_MINIMA <= duracion <= DURACION_MAXIMA:
        return jsonify(error=f"Duración debe estar entre {DURACION_MINIMA} y {DURACION_MAXIMA} segundos"), 400

    with _candado:
        if _estado["estado"] == "ejecutando":
            return jsonify(error="Ya hay una prueba de carga en curso"), 409
        _estado.update(
            estado="ejecutando",
            usuarios=usuarios,
            duracion=duracion,
            inicio=time.time(),
            fin=None,
            resultado=None,
            error=None,
        )
    threading.Thread(target=_correr, args=(usuarios, duracion), daemon=True).start()
    return jsonify(estado="ejecutando", usuarios=usuarios, duracion=duracion), 202


@app.get("/estado")
def estado():
    return jsonify(_estado_copiado())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
