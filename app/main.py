"""API de notas. Cada instancia mantiene sus estudiantes en memoria."""
from threading import Lock

from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, jsonify, request

from app.calculadora import calcular_definitiva, determinar_estado
from app.reportes import exportar_a_s3, generar_csv
from infra.setup_aws import NOMBRE_BUCKET, crear_cliente_s3


def datos_json():
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


def crear_app(cliente_s3=None):
    app = Flask(__name__)
    estudiantes = {}
    bloqueo = Lock()

    @app.get("/salud")
    def salud():
        return jsonify(estado="ok")

    @app.post("/estudiantes")
    def crear_estudiante():
        datos = datos_json()
        campos = ("nombre", "codigo")
        if not all(isinstance(datos.get(c), str) and datos[c].strip() for c in campos):
            return jsonify(error="Nombre y código deben ser textos con contenido"), 400
        with bloqueo:
            identificador = len(estudiantes) + 1
            estudiante = {c: datos[c].strip() for c in campos}
            estudiante["id"] = identificador
            estudiantes[identificador] = estudiante
            return jsonify(estudiante), 201

    @app.post("/estudiantes/<int:identificador>/notas")
    def registrar_notas(identificador):
        datos = datos_json()
        with bloqueo:
            if identificador not in estudiantes:
                return jsonify(error="Estudiante inexistente"), 404
            try:
                definitiva = calcular_definitiva(*(datos.get(f"momento{i}") for i in (1, 2, 3)))
            except (TypeError, ValueError) as error:
                return jsonify(error=str(error)), 400
            resumen = dict(definitiva=definitiva, estado=determinar_estado(definitiva))
            estudiantes[identificador].update(resumen)
        return jsonify(id=identificador, **resumen), 201

    @app.get("/estudiantes/<int:identificador>/promedio")
    def consultar_promedio(identificador):
        with bloqueo:
            estudiante = estudiantes.get(identificador, {})
            if "definitiva" not in estudiante:
                return jsonify(error="Estudiante inexistente o sin notas"), 404
            return jsonify({c: estudiante[c] for c in ("id", "nombre", "definitiva", "estado")})

    @app.post("/reportes/exportar")
    def exportar_reporte():
        with bloqueo:
            filas = [e.copy() for e in estudiantes.values() if "definitiva" in e]
        try:
            cliente = cliente_s3 if cliente_s3 is not None else crear_cliente_s3()
            archivo = exportar_a_s3(generar_csv(filas), cliente, NOMBRE_BUCKET)
        except (ClientError, BotoCoreError):
            app.logger.exception("Error al exportar el reporte")
            return jsonify(error="El almacenamiento del reporte no está disponible"), 503
        return jsonify(bucket=NOMBRE_BUCKET, archivo=archivo), 201

    return app


app = crear_app()
