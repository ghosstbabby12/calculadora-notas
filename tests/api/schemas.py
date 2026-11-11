"""Contratos JSON (JSON Schema) de las respuestas de la API.

Persona B los usa en tests/api para validar que la API cumple el contrato
acordado con el equipo. Persona C los puede reutilizar en el pipeline.
"""

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

# GET /promedio devuelve exactamente lo mismo que POST /notas.
PROMEDIO_RESPUESTA = NOTAS_REGISTRO

ERROR_RESPUESTA = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {"type": "string", "minLength": 1},
    },
    "additionalProperties": True,
}

HEALTH_RESPUESTA = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {"type": "string", "const": "ok"},
    },
    "additionalProperties": True,
}
