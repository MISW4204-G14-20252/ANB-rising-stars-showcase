import subprocess
from pathlib import Path
from celery import Celery
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from src.models.db_models import Video
from src.db.database import get_db
from src.utils.s3_utils import upload_to_s3, download_from_s3
import os

# =======================================================
# CONFIGURACIÓN BASE
# =======================================================
BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("tasks", broker=BROKER_URL)

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = Path("/tmp")  # Carpeta temporal dentro del contenedor o VM

# Si existe el watermark local, úsalo; si no, podrías cargarlo desde S3 si es necesario
WATERMARK_PATH = BASE_DIR / "videos" / "nba-rs-normalized.mp4"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =======================================================
# TAREA PRINCIPAL
# =======================================================
@celery.task(name="tasks.process_video")
def process_video(video: dict):
    """
    Descarga un video desde S3, lo procesa (trim + watermark),
    sube la versión final a S3 y actualiza el estado en la BD.
    """
    start_time = datetime.now()
    db: Session = None

    try:
        # --- Inicialización ---
        filename = Path(video.get("filename")).name
        s3_key_input = video.get("filename")  # p.ej. 'unprocessed-videos/abc123.mp4'
        name = Path(filename).stem

        local_source = TMP_DIR / filename
        local_tmp = TMP_DIR / f"{name}.tmp.mp4"
        local_output = TMP_DIR / f"{name}_processed.mp4"

        # --- 1️⃣ Descargar desde S3 ---
        logger.info(f"⬇️ Descargando {s3_key_input} desde S3...")
        if not download_from_s3(s3_key_input, local_source):
            raise Exception(f"No se pudo descargar el archivo desde S3: {s3_key_input}")

        # --- 2️⃣ Procesar con FFmpeg ---
        logger.info(f"🎬 Procesando video {filename}...")

        # Paso 1: trim, normalización, resize
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

        # Paso 2: concatenar watermark + clip + watermark
        logger.info("🎞️ Concatenando con intro y outro (watermark)...")

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

        # --- 3️⃣ Subir resultado a S3 ---
        processed_key = f"processed-videos/{name}_processed.mp4"
        logger.info(f"⬆️ Subiendo resultado a S3: {processed_key}")
        upload_success = upload_to_s3(local_output, processed_key)
        if not upload_success:
            raise Exception("Error subiendo el video procesado a S3.")

        # --- 4️⃣ Actualizar base de datos ---
        logger.info("🗂️ Actualizando base de datos...")
        db = next(get_db())
        db.query(Video).filter(Video.id == video.get("id")).update(
            {
                "status": "processed",
                "processed_at": datetime.now(),
                "filename": processed_key,  # reemplaza el path por el nuevo key procesado
            }
        )
        db.commit()

        logger.info("✅ Video procesado y actualizado correctamente.")

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
        error_msg = f"❌ Error general procesando {filename}: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "file": filename,
            "timestamp": datetime.now().isoformat(),
        }

    finally:
        # --- 5️⃣ Limpieza de archivos locales ---
        for f in [local_source, local_tmp, local_output]:
            try:
                if f.exists():
                    f.unlink()
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Error eliminando archivo temporal {f}: {cleanup_error}")

        if db:
            db.close()


# =======================================================
# CLI DE PRUEBA
# =======================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Video Processing Worker (S3 Version)")
    print("=" * 60)
    print("Uso:")
    print("  celery -A worker.video_processor_task worker --loglevel=info")
    print()
    print("Para test manual:")
    print("  from worker.video_processor_task import process_video")
    print("  process_video.delay({'id': 1, 'filename': 'unprocessed-videos/test.mp4'})")
    print("=" * 60)