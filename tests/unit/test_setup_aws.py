"""Pruebas unitarias de infra/setup_aws.py con un cliente S3 simulado."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from infra.setup_aws import (
    ENDPOINT_POR_DEFECTO,
    NOMBRE_BUCKET,
    crear_bucket_si_no_existe,
    crear_cliente_s3,
)


def _error_no_encontrado():
    return ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")


def test_crea_el_bucket_cuando_no_existe():
    # Arrange
    cliente_s3 = MagicMock()
    cliente_s3.head_bucket.side_effect = _error_no_encontrado()

    # Act
    creado = crear_bucket_si_no_existe(cliente_s3)

    # Assert
    assert creado is True
    cliente_s3.create_bucket.assert_called_once_with(Bucket=NOMBRE_BUCKET)


def test_no_crea_el_bucket_cuando_ya_existe():
    # Arrange
    cliente_s3 = MagicMock()

    # Act
    creado = crear_bucket_si_no_existe(cliente_s3)

    # Assert
    assert creado is False
    cliente_s3.create_bucket.assert_not_called()


@patch.dict("os.environ", {}, clear=True)
@patch("infra.setup_aws.boto3.client")
def test_cliente_usa_localstack_por_defecto(mock_client):
    # Arrange: entorno sin variables AWS_*

    # Act
    crear_cliente_s3()

    # Assert
    argumentos = mock_client.call_args.kwargs
    assert argumentos["endpoint_url"] == ENDPOINT_POR_DEFECTO
    assert argumentos["aws_access_key_id"] == "test"
    assert argumentos["region_name"] == "us-east-1"


@patch.dict("os.environ", {"AWS_ENDPOINT_URL": "http://localstack:4566"}, clear=True)
@patch("infra.setup_aws.boto3.client")
def test_cliente_respeta_variable_aws_endpoint_url(mock_client):
    # Arrange: AWS_ENDPOINT_URL apunta al servicio de Docker Compose

    # Act
    crear_cliente_s3()

    # Assert
    assert mock_client.call_args.kwargs["endpoint_url"] == "http://localstack:4566"
