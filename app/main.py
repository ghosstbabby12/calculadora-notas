"""API REST de la calculadora de notas (Persona B).

Expone la lógica de negocio de ``app.calculadora`` mediante HTTP:

- POST /estudiantes -> 201 (crea un estudiante)
- POST /estudiantes/<id>/notas -> 201 o 400/404 (registra momentos y calcula)
- GET /estudiantes/<id>/promedio -> 200 o 404 (devuelve definitiva y estado)

El almacenamiento es en memoria (dict) para mantener el proyecto simple
y testable. Se usa ``create_app`` (factory) para que las pruebas puedan
crear instancias aisladas sin red.
"""

from flask import Flask, jsonify, request

from app.calculadora import calcular_definitiva, determinar_estado

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


def create_app():
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.post("/estudiantes")
    def crear_estudiante():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify({"error": "El cuerpo debe ser un JSON con 'nombre'"}), 400
        nombre = datos.get("nombre")
        codigo = datos.get("codigo", "")
        if not isinstance(nombre, str) or not nombre.strip():
            return jsonify({"error": "El campo 'nombre' es obligatorio y debe ser texto no vacío"}), 400
        if codigo is not None and codigo != "" and not isinstance(codigo, str):
            return jsonify({"error": "El campo 'codigo' debe ser texto"}), 400
        id_estudiante = _nuevo_id()
        estudiante = {
            "id": id_estudiante,
            "codigo": codigo or "",
            "nombre": nombre.strip(),
            "notas": None,
            "definitiva": None,
            "estado": None,
        }
        store[id_estudiante] = estudiante
        return jsonify({"id": id_estudiante, "codigo": estudiante["codigo"], "nombre": estudiante["nombre"]}), 201

    @app.post("/estudiantes/<int:id_estudiante>/notas")
    def registrar_notas(id_estudiante):
        estudiante = store.get(id_estudiante)
        if estudiante is None:
            return jsonify({"error": "Estudiante no encontrado"}), 404
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify({"error": "El cuerpo debe ser un JSON con 'm1', 'm2' y 'm3'"}), 400
        # Se aceptan alias momento1/2/3 por comodidad, pero el contrato oficial es m1/m2/m3.
        m1 = datos.get("m1", datos.get("momento1"))
        m2 = datos.get("m2", datos.get("momento2"))
        m3 = datos.get("m3", datos.get("momento3"))
        if m1 is None or m2 is None or m3 is None:
            return jsonify({"error": "Se requieren los campos 'm1', 'm2' y 'm3'"}), 400
        try:
            definitiva = calcular_definitiva(m1, m2, m3)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        estado = determinar_estado(definitiva)
        estudiante["notas"] = {"m1": float(m1), "m2": float(m2), "m3": float(m3)}
        estudiante["definitiva"] = definitiva
        estudiante["estado"] = estado
        return jsonify({"id": id_estudiante, "definitiva": definitiva, "estado": estado}), 201

    @app.get("/estudiantes/<int:id_estudiante>/promedio")
    def obtener_promedio(id_estudiante):
        estudiante = store.get(id_estudiante)
        if estudiante is None:
            return jsonify({"error": "Estudiante no encontrado"}), 404
        if estudiante["definitiva"] is None:
            return jsonify({"error": "El estudiante aún no tiene notas registradas"}), 404
        return (
            jsonify(
                {"id": id_estudiante, "definitiva": estudiante["definitiva"], "estado": estudiante["estado"]}
            ),
            200,
        )

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover
    # host 0.0.0.0 para que Docker pueda exponer el puerto.
    app.run(host="0.0.0.0", port=5000)
