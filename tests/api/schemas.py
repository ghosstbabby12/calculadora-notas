def objeto(campos):
    return {"type": "object", "properties": campos, "required": list(campos),
            "additionalProperties": False}


TEXTO = {"type": "string", "minLength": 1}
ID = {"type": "integer", "minimum": 1}
RESUMEN = {"definitiva": {"type": "number", "minimum": 0, "maximum": 5},
           "estado": {"enum": ["APROBADO", "HABILITA", "REPROBADO"]}}
ESTUDIANTE = objeto({"id": ID, "nombre": TEXTO, "codigo": TEXTO})
NOTAS = objeto({"id": ID, **RESUMEN})
PROMEDIO = objeto({"id": ID, "nombre": TEXTO, **RESUMEN})
ERROR = objeto({"error": TEXTO})
SALUD = objeto({"estado": {"const": "ok"}})
REPORTE = objeto({"bucket": TEXTO, "archivo": TEXTO})
