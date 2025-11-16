import boto3
from botocore.exceptions import ClientError
import logging
import json
import os

logger = logging.getLogger(__name__)

sqs_client = boto3.client("sqs")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")


def send_to_sqs(message: dict) -> bool:
    """
    Envía un mensaje a la cola SQS.
    El mensaje debe ser un dict y será convertido a JSON.
    """
    try:
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message)
        )
        logger.info(" Mensaje enviado a SQS correctamente.")
        return True

    except ClientError as e:
        logger.error(f" Error enviando mensaje a SQS: {e}")
        return False


def receive_from_sqs(max_messages: int = 1, wait_time: int = 20):
    """
    Recibe mensajes desde SQS usando long polling.
    Retorna una lista de diccionarios con:
        - body: mensaje parseado (dict)
        - receipt: handle necesario para borrar el mensaje

    Ejemplo de retorno:
    [
        { "body": {...}, "receipt": "XXXX" },
        ...
    ]
    """
    try:
        response = sqs_client.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_time,
            MessageAttributeNames=["All"]
        )

        messages = response.get("Messages", [])

        parsed = []
        for msg in messages:
            parsed.append({
                "body": json.loads(msg["Body"]),
                "receipt": msg["ReceiptHandle"]
            })

        if parsed:
            logger.info(f" {len(parsed)} mensaje(s) recibido(s) desde SQS.")

        return parsed

    except ClientError as e:
        logger.error(f" Error recibiendo mensajes de SQS: {e}")
        return []


def delete_from_sqs(receipt_handle: str) -> bool:
    """
    Elimina un mensaje de SQS usando su receipt handle.
    Esto debe hacerse solo después de procesar el mensaje correctamente.
    """
    try:
        sqs_client.delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle
        )
        logger.info(" Mensaje eliminado de SQS correctamente.")
        return True

    except ClientError as e:
        logger.error(f" Error eliminando mensaje de SQS: {e}")
        return False
