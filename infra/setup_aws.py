"""Aprovisionamiento de infraestructura (IaC) en LocalStack con Boto3.

Crea el bucket S3 "reportes-notas" si todavía no existe.
Es idempotente: se puede ejecutar varias veces sin error.

Uso:
    python infra/setup_aws.py
    AWS_ENDPOINT_URL=http://localstack:4566 python infra/setup_aws.py
"""

import os

import boto3
from botocore.exceptions import ClientError

ENDPOINT_POR_DEFECTO = "http://localhost:4566"
REGION = "us-east-1"
CREDENCIAL_LOCALSTACK = "test"
NOMBRE_BUCKET = "reportes-notas"


def crear_cliente_s3():
    """Crea un cliente S3 apuntando al endpoint configurado (LocalStack por defecto)."""
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", ENDPOINT_POR_DEFECTO),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", CREDENCIAL_LOCALSTACK),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", CREDENCIAL_LOCALSTACK),
        region_name=os.getenv("AWS_DEFAULT_REGION", REGION),
    )


def bucket_existe(cliente_s3, bucket):
    """Indica si el bucket existe consultándolo con head_bucket."""
    try:
        cliente_s3.head_bucket(Bucket=bucket)
        return True
    except ClientError:
        return False


def crear_bucket_si_no_existe(cliente_s3, bucket=NOMBRE_BUCKET):
    """Crea el bucket solo si no existe. Devuelve True si lo creó."""
    if bucket_existe(cliente_s3, bucket):
        print(f"El bucket '{bucket}' ya existe, no se hace nada.")
        return False
    # En us-east-1 no se envía LocationConstraint.
    cliente_s3.create_bucket(Bucket=bucket)
    print(f"Bucket '{bucket}' creado correctamente.")
    return True


def main():
    crear_bucket_si_no_existe(crear_cliente_s3())


if __name__ == "__main__":
    main()
