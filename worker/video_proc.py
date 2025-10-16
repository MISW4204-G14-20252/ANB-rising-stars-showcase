import subprocess
from pathlib import Path
from celery import Celery
from datetime import datetime
import json
import logging

celery = Celery("tasks", broker="redis://localhost:6379/0")

BASE_DIR = Path(__file__).parent.parent
UNPROCESSED_DIR = BASE_DIR / "videos" / "unprocessed-videos"
PROCESSED_DIR = BASE_DIR / "videos" / "processed-videos"

UNPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def tiene_audio(video_path):
    """Detecta si un video tiene stream de audio"""
    try:
        resultado = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        info = json.loads(resultado.stdout)
        return any(
            stream["codec_type"] == "audio" for stream in info.get("streams", [])
        )
    except Exception as _:
        return False


@celery.task(name="tasks.procesar_video")
def procesar_video(nombre_archivo):
    def asegurar_audio(video_path: Path):
        """Agrega audio silencioso si el video no tiene pista de audio."""
        if not tiene_audio(video_path):
            logging.info(
                f"{video_path.name} no tiene audio: agregando pista silenciosa"
            )
            tmp_path = video_path.with_suffix(".audiofix.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    str(video_path),
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-shortest",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-y",
                    str(tmp_path),
                ],
                check=True,
            )
            video_path.unlink(missing_ok=True)
            tmp_path.rename(video_path)
            logging.info(f"Audio silencioso agregado a {video_path.name}")

    try:
        name = nombre_archivo.split(".")[0]
        origen = UNPROCESSED_DIR / nombre_archivo
        origen_tmp = UNPROCESSED_DIR / f"{name}.tmp.mp4"
        watermark_path = BASE_DIR / "videos" / "nba-rs.mp4"
        destino = PROCESSED_DIR / f"{name}_processed.mp4"

        # Validar existencia del archivo
        if not origen.exists():
            msg = f"Archivo no encontrado: {origen}"
            logging.error(msg)
            return {
                "success": False,
                "error": msg,
                "timestamp": datetime.now().isoformat(),
            }

        logging.info(f"Procesando video: {nombre_archivo}")

        logging.info("Recortando a 30 s y convirtiendo a 16:9")
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(origen),
                "-t",
                "30",
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
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
                str(origen_tmp),
            ],
            check=True,
        )

        asegurar_audio(origen_tmp)
        asegurar_audio(watermark_path)

        logging.info("Normalizando clips para concatenación")
        normalized_watermark = UNPROCESSED_DIR / "watermark_norm.mp4"
        normalized_input = UNPROCESSED_DIR / f"{name}_norm.mp4"

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(watermark_path),
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
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
                "-y",
                str(normalized_watermark),
            ],
            check=True,
        )

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(origen_tmp),
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
                "-y",
                str(normalized_input),
            ],
            check=True,
        )

        logging.info("Concatenando clips (marca de agua + original + marca de agua)")
        concat_list = UNPROCESSED_DIR / f"concat_{name}.txt"
        concat_list.write_text(
            f"file '{normalized_watermark}'\n"
            f"file '{normalized_input}'\n"
            f"file '{normalized_watermark}'\n"
        )

        subprocess.run(
            [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
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
                str(destino),
            ],
            check=True,
        )

        logging.info(f"Video procesado correctamente: {destino}")

        return {
            "success": True,
            "archivo": nombre_archivo,
            "origen": str(origen),
            "destino": str(destino),
            "timestamp": datetime.now().isoformat(),
        }

    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg error procesando {nombre_archivo}: {e.stderr or e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "archivo": nombre_archivo,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        error_msg = f"Error procesando {nombre_archivo}: {e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "archivo": nombre_archivo,
            "timestamp": datetime.now().isoformat(),
        }

    finally:
        # Limpieza de archivos temporales
        for path in [origen_tmp, normalized_watermark, normalized_input, concat_list]:
            if path.exists():
                try:
                    path.unlink()
                    logging.info(f"Eliminado temporal: {path.name}")
                except Exception:
                    pass


if __name__ == "__main__":
    print("=" * 60)
    print("Sistema de Procesamiento de Videos")
    print("=" * 60)
    print(f"\nDirectorio de videos sin procesar: {UNPROCESSED_DIR}")
    print(f"Directorio de videos procesados: {PROCESSED_DIR}")
    print("\nFunciones disponibles:")
    print("  - procesar_video('nombre.mp4')")
    print("\nPara usar con Celery:")
    print("  - procesar_video.delay('nombre.mp4')")
    print("=" * 60)
