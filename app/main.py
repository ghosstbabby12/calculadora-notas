"""API REST de la calculadora de notas (Persona B, integrada con Persona C).

Contrato canónico (enunciado del curso):
- POST /estudiantes -> 201 (requiere nombre y codigo no vacíos)
- POST /estudiantes/{id}/notas -> 201 o 400/404 (acepta m1/m2/m3 y alias momento1/2/3)
- GET /estudiantes/{id}/promedio -> 200 o 404 (devuelve id, nombre, definitiva y estado)
- GET /health y GET /salud -> 200 (alias para CI local y workflows)
- POST /reportes/exportar -> 201 o 503 (exporta CSV a S3, aporte Persona C sobre datos de A)

Almacén en memoria con Lock para peticiones concurrentes (Locust).
``crear_app(cliente_s3=None)`` permite inyectar un mock en pruebas unitarias.
"""

from threading import Lock

from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, jsonify, request

from app.calculadora import calcular_definitiva, determinar_estado
from app.reportes import exportar_a_s3, generar_csv
from infra.setup_aws import NOMBRE_BUCKET, crear_cliente_s3

# Almacén en memoria: {id: {"id", "codigo", "nombre", "notas", "definitiva", "estado"}}
store = {}
_next_id = 1


def reset_store():
    """Reinicia el almacén en memoria. Solo se usa en pruebas."""
    global store, _next_id
    store = {}
    _next_id = 1


def _nuevo_id():
    global _next_id
    id_actual = _next_id
    _next_id += 1
    return id_actual


def datos_json():
    """Devuelve el cuerpo JSON como dict, o {} si no es un objeto JSON."""
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


def crear_app(cliente_s3=None):
    app = Flask(__name__)
    bloqueo = Lock()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.get("/salud")
    def salud():
        return jsonify({"estado": "ok"}), 200

    @app.post("/estudiantes")
    def crear_estudiante():
        datos = datos_json()
        # Nombre y código obligatorios (contrato estricto de Persona C,
        # compatible con las pruebas de Persona B que siempre los envían).
        if not all(isinstance(datos.get(c), str) and datos[c].strip() for c in ("nombre", "codigo")):
            return jsonify({"error": "Los campos 'nombre' y 'codigo' son obligatorios y deben ser texto no vacío"}), 400
        with bloqueo:
            id_estudiante = _nuevo_id()
            estudiante = {
                "id": id_estudiante,
                "nombre": datos["nombre"].strip(),
                "codigo": datos["codigo"].strip(),
                "notas": None,
                "definitiva": None,
                "estado": None,
            }
            store[id_estudiante] = estudiante
            return jsonify({"id": id_estudiante, "nombre": estudiante["nombre"], "codigo": estudiante["codigo"]}), 201

    @app.post("/estudiantes/<int:id_estudiante>/notas")
    def registrar_notas(id_estudiante):
        datos = datos_json()
        with bloqueo:
            estudiante = store.get(id_estudiante)
            if estudiante is None:
                return jsonify({"error": "Estudiante no encontrado"}), 404
            # Contrato oficial m1/m2/m3 + alias momento1/2/3 (compatibilidad B y C).
            m1 = datos.get("m1", datos.get("momento1"))
            m2 = datos.get("m2", datos.get("momento2"))
            m3 = datos.get("m3", datos.get("momento3"))
            if m1 is None or m2 is None or m3 is None:
                return jsonify({"error": "Se requieren las tres notas ('m1', 'm2', 'm3' o 'momento1/2/3')"}), 400
            try:
                definitiva = calcular_definitiva(m1, m2, m3)
            except (TypeError, ValueError) as exc:
                return jsonify({"error": str(exc)}), 400
            estado = determinar_estado(definitiva)
            # Solo se actualiza si el cálculo fue válido (una entrada inválida
            # conserva las notas anteriores).
            estudiante["notas"] = {"m1": float(m1), "m2": float(m2), "m3": float(m3)}
            estudiante["definitiva"] = definitiva
            estudiante["estado"] = estado
            return jsonify({"id": id_estudiante, "definitiva": definitiva, "estado": estado}), 201

    @app.get("/estudiantes/<int:id_estudiante>/promedio")
    def obtener_promedio(id_estudiante):
        with bloqueo:
            estudiante = store.get(id_estudiante)
            if estudiante is None or estudiante["definitiva"] is None:
                return jsonify({"error": "Estudiante inexistente o sin notas registradas"}), 404
            return (
                jsonify(
                    {
                        "id": id_estudiante,
                        "nombre": estudiante["nombre"],
                        "definitiva": estudiante["definitiva"],
                        "estado": estudiante["estado"],
                    }
                ),
                200,
            )

    @app.post("/reportes/exportar")
    def exportar_reporte():
        # Aporte Persona C: exporta el CSV de Persona A a S3/LocalStack.
        with bloqueo:
            filas = [e.copy() for e in store.values() if e["definitiva"] is not None]
        try:
            cliente = cliente_s3 if cliente_s3 is not None else crear_cliente_s3()
            archivo = exportar_a_s3(generar_csv(filas), cliente, NOMBRE_BUCKET)
        except (ClientError, BotoCoreError, Exception):
            app.logger.exception("Error al exportar el reporte")
            return jsonify({"error": "El almacenamiento del reporte no está disponible"}), 503
        return jsonify({"bucket": NOMBRE_BUCKET, "archivo": archivo}), 201

    return app


app = crear_app()

if __name__ == "__main__":  # pragma: no cover
    # host 0.0.0.0 para que Docker pueda exponer el puerto.
    app.run(host="0.0.0.0", port=5000)
