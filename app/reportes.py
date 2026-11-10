"""Generación de reportes CSV y exportación a S3 (LocalStack o AWS).

El cliente S3 se recibe por parámetro (inyección de dependencias), así las
pruebas unitarias pueden usar un objeto simulado (mock) sin tocar la red.
"""

import csv
import io
from datetime import datetime

COLUMNAS_REPORTE = ["codigo", "nombre", "definitiva", "estado"]
PREFIJO_ARCHIVO = "reporte_notas_"
FORMATO_FECHA = "%Y%m%d_%H%M%S"
TIPO_CONTENIDO_CSV = "text/csv"


def generar_csv(estudiantes):
    """Convierte una lista de estudiantes (dicts) en texto CSV.

    Cada estudiante debe tener las llaves: codigo, nombre, definitiva, estado.
    Llaves adicionales (por ejemplo id o notas) se ignoran.
    """
    buffer = io.StringIO()
    escritor = csv.DictWriter(
        buffer, fieldnames=COLUMNAS_REPORTE, extrasaction="ignore", lineterminator="\n"
    )
    escritor.writeheader()
    escritor.writerows(estudiantes)
    return buffer.getvalue()


def generar_nombre_archivo(momento=None):
    """Devuelve el nombre reporte_notas_AAAAMMDD_HHMMSS.csv para el momento dado."""
    momento = momento or datetime.now()
    return f"{PREFIJO_ARCHIVO}{momento.strftime(FORMATO_FECHA)}.csv"


def exportar_a_s3(contenido_csv, cliente_s3, bucket):
    """Sube el contenido CSV al bucket indicado y devuelve el nombre del archivo."""
    nombre_archivo = generar_nombre_archivo()
    cliente_s3.put_object(
        Bucket=bucket,
        Key=nombre_archivo,
        Body=contenido_csv.encode("utf-8"),
        ContentType=TIPO_CONTENIDO_CSV,
    )
    return nombre_archivo
