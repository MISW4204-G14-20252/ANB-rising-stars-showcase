import subprocess
from pathlib import Path
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from src.models.db_models import Video
from src.db.database import get_db
from src.utils.s3_utils import upload_to_s3, download_from_s3
import os
from src.utils.sqs_utils import receive_from_sqs, delete_from_sqs


BASE_DIR = Path(__file__).parent.parent
TMP_DIR = Path("videos/unprocessed-videos/")

WATERMARK_PATH = BASE_DIR / "videos" / "nba-rs-normalized.mp4"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_video(video: dict):
    """
    Descarga un video desde S3, lo procesa (trim + watermark),
    sube la versión final a S3 y actualiza el estado en la BD.
    """
    start_time = datetime.now()
    db: Session = None

    try:
        filename = Path(video.get("filename")).name
        s3_key_input = video.get("filename")
        name = Path(filename).stem

        local_source = TMP_DIR / filename
        local_tmp = TMP_DIR / f"{name}.tmp.mp4"
        local_output = TMP_DIR / f"{name}_processed.mp4"

        logger.info(f"Descargando {s3_key_input} desde S3...")
        if not download_from_s3(s3_key_input, local_source):
            raise Exception(f"No se pudo descargar el archivo desde S3: {s3_key_input}")

        logger.info(f"Procesando video {filename}...")

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(local_source),
                "-t",
                "30",
                "-vf",
                "fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-b:a",
                "128k",
                "-y",
                "-loglevel",
                "error",
                str(local_tmp),
            ],
            check=True,
        )

        logger.info("Concatenando con intro y outro (watermark)...")

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(WATERMARK_PATH),
                "-i",
                str(local_tmp),
                "-i",
                str(WATERMARK_PATH),
                "-filter_complex",
                "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-y",
                "-loglevel",
                "error",
                str(local_output),
            ],
            check=True,
        )

        processed_key = f"processed-videos/{name}_processed.mp4"
        logger.info(f"Subiendo resultado a S3: {processed_key}")
        upload_success = upload_to_s3(local_output, processed_key)
        if not upload_success:
            raise Exception("Error subiendo el video procesado a S3.")

        logger.info("Actualizando base de datos...")
        db = next(get_db())
        db.query(Video).filter(Video.id == video.get("id")).update(
            {
                "status": "processed",
                "processed_at": datetime.now(),
                "filename": processed_key,
            }
        )
        db.commit()

        logger.info("Video procesado y actualizado correctamente.")

        return {
            "success": True,
            "file": filename,
            "processed_key": processed_key,
            "timestamp": datetime.now().isoformat(),
            "processing_time_seconds": round(
                (datetime.now() - start_time).total_seconds(), 2
            ),
        }

    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg error procesando {filename}: {e.stderr or e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "file": filename,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        error_msg = f"Error general procesando {filename}: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "file": filename,
            "timestamp": datetime.now().isoformat(),
        }

    finally:
        for f in [local_source, local_tmp, local_output]:
            try:
                if f.exists():
                    f.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Error eliminando archivo temporal {f}: {cleanup_error}")

        if db:
            db.close()


# =======================================================
# LOOP PRINCIPAL PARA LEER DE SQS
# =======================================================
def run_sqs_worker(poll_interval=10):
    """
    Bucle principal que escucha la cola SQS y procesa mensajes uno a uno.
    poll_interval: segundos entre revisiones si la cola está vacía.
    """
    logger.info("Iniciando worker de procesamiento de videos (SQS)...")

    while True:
        try:
            messages = receive_from_sqs(max_messages=1, wait_time=10)
            if not messages:
                logger.debug("No hay mensajes en la cola. Esperando...")
                import time
                time.sleep(poll_interval)
                continue

            for msg in messages:
                body = msg.get("Body")
                if not body:
                    logger.warning("Mensaje vacío, se elimina.")
                    delete_from_sqs(msg["ReceiptHandle"])
                    continue

                import json
                try:
                    video_data = json.loads(body)
                except Exception as e:
                    logger.error(f"Error parseando JSON del mensaje: {e}")
                    delete_from_sqs(msg["ReceiptHandle"])
                    continue

                logger.info(f"Procesando video ID={video_data.get('id')}, archivo={video_data.get('filename')}")
                result = process_video(video_data)

                if result.get("success"):
                    logger.info(f"✅ Procesado correctamente: {video_data.get('filename')}")
                else:
                    logger.error(f"❌ Falló procesamiento: {result.get('error')}")

                # Eliminar mensaje de la cola (importante para no reprocesar)
                delete_from_sqs(msg["ReceiptHandle"])

        except KeyboardInterrupt:
            logger.info("Worker detenido manualmente.")
            break

        except Exception as e:
            logger.error(f"Error general en el loop SQS: {e}")
            import time
            time.sleep(poll_interval)


if __name__ == "__main__":
    print("=" * 60)
    print("Video Processing Worker (SQS Version)")
    print("=" * 60)
    run_sqs_worker()