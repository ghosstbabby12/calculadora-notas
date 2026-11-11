"""Contratos JSON (JSON Schema) de las respuestas de la API.

Unifica los contratos de Persona B (enunciado: m1/m2/m3, /health) y
Persona C (momento1/2/3, /salud, exportación a S3). Ambos estilos son
válidos; la API acepta los dos.
"""


def _objeto(campo_tipos):
    return {
        "type": "object",
        "properties": campo_tipos,
        "required": list(campo_tipos),
        "additionalProperties": False,
    }


TEXTO = {"type": "string", "minLength": 1}
ID = {"type": "integer", "minimum": 1}
RESUMEN = {
    "definitiva": {"type": "number", "minimum": 0.0, "maximum": 5.0},
    "estado": {"type": "string", "enum": ["APROBADO", "HABILITA", "REPROBADO"]},
}

# --- Contratos estrictos (Persona C, additionalProperties False) ---
ESTUDIANTE = _objeto({"id": ID, "nombre": TEXTO, "codigo": TEXTO})
NOTAS = _objeto({"id": ID, **RESUMEN})
PROMEDIO = _objeto({"id": ID, "nombre": TEXTO, **RESUMEN})
ERROR = _objeto({"error": TEXTO})
SALUD = _objeto({"estado": {"const": "ok"}})
REPORTE = _objeto({"bucket": TEXTO, "archivo": TEXTO})

# --- Aliases compatibles (Persona B, additionalProperties True) ---
ESTUDIANTE_CREACION = {
    "type": "object",
    "required": ["id", "nombre"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "codigo": {"type": "string"},
        "nombre": {"type": "string", "minLength": 1},
    },
    "additionalProperties": True,
}

NOTAS_REGISTRO = {
    "type": "object",
    "required": ["id", "definitiva", "estado"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "definitiva": {"type": "number", "minimum": 0.0, "maximum": 5.0},
        "estado": {"type": "string", "enum": ["APROBADO", "HABILITA", "REPROBADO"]},
    },
    "additionalProperties": True,
}

# GET /promedio devuelve id, nombre, definitiva y estado.
PROMEDIO_RESPUESTA = {
    "type": "object",
    "required": ["id", "definitiva", "estado"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "nombre": {"type": "string", "minLength": 1},
        "definitiva": {"type": "number", "minimum": 0.0, "maximum": 5.0},
        "estado": {"type": "string", "enum": ["APROBADO", "HABILITA", "REPROBADO"]},
    },
    "additionalProperties": True,
}

ERROR_RESPUESTA = {
    "type": "object",
    "required": ["error"],
    "properties": {"error": {"type": "string", "minLength": 1}},
    "additionalProperties": True,
}

HEALTH_RESPUESTA = {
    "type": "object",
    "required": ["status"],
    "properties": {"status": {"type": "string", "const": "ok"}},
    "additionalProperties": True,
}
