import boto3
from botocore.exceptions import ClientError
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)
s3_client = boto3.client("s3")

BUCKET_NAME = os.getenv("S3_BUCKET", "anb-rising-stars-videos-gr14")


def upload_to_s3(local_path: Path, s3_key: str) -> bool:
    """Sube un archivo local a S3."""
    try:
        s3_client.upload_file(str(local_path), BUCKET_NAME, s3_key)
        logger.info(f"✅ Archivo subido a S3: {s3_key}")
        return True
    except ClientError as e:
        logger.error(f"❌ Error subiendo a S3: {e}")
        return False


def download_from_s3(s3_key: str, local_path: Path) -> bool:
    """Descarga un archivo desde S3."""
    try:
        s3_client.download_file(BUCKET_NAME, s3_key, str(local_path))
        logger.info(f"⬇️ Archivo descargado desde S3: {s3_key}")
        return True
    except ClientError as e:
        logger.error(f"❌ Error descargando desde S3: {e}")
        return False


def delete_from_s3(s3_key: str) -> bool:
    """Elimina un objeto del bucket S3."""
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        logger.info(f"🗑️ Archivo eliminado de S3: {s3_key}")
        return True
    except ClientError as e:
        logger.error(f"❌ Error eliminando de S3: {e}")
        return False