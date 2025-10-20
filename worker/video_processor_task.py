import subprocess
from pathlib import Path
from celery import Celery
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from src.models.db_models import Video

from src.db.database import get_db

import os

BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("tasks", broker=BROKER_URL)

BASE_DIR = Path(__file__).parent.parent
UNPROCESSED_DIR = BASE_DIR / "videos" / "unprocessed-videos"
PROCESSED_DIR = BASE_DIR / "videos" / "processed-videos"

UNPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


@celery.task(name="tasks.process_video")
def process_video(video: dict):
    try:
        start_time = datetime.now()
        filename = video.get("filename")

        name = filename.split(".")[0]
        source = UNPROCESSED_DIR / filename
        source_tmp = UNPROCESSED_DIR / f"{name}.tmp.mp4"
        watermark_path = BASE_DIR / "videos" / "nba-rs-normalized.mp4"
        destination = PROCESSED_DIR / f"{name}_processed.mp4"

        # Validate file existence
        if not source.exists():
            msg = f"File not found: {source}"
            logging.error(msg)
            return {
                "success": False,
                "error": msg,
                "timestamp": datetime.now().isoformat(),
            }

        logging.info(f"Processing video: {filename}")

        logging.info("Trimming to 30s, converting to 16:9 and normalizing")

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(source),
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
                str(source_tmp),
            ],
            check=True,
        )

        logging.info("Concatenating clips (watermark + original + watermark)")

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(watermark_path),
                "-i",
                str(source_tmp),
                "-i",
                str(watermark_path),
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
                str(destination),
            ],
            check=True,
        )
        logging.info("Video processed successfully")

        logging.info("Creating database session")
        db: Session = next(get_db())

        logging.info("Updating database status")

        db.query(Video).filter(Video.id == video.get("id")).update(
            {"status": "processed", "processed_at": datetime.now()}
        )
        db.commit()

        logging.info("Database status updated successfully")

        return {
            "success": True,
            "file": filename,
            "source": str(source),
            "destination": str(destination),
            "timestamp": datetime.now().isoformat(),
            "processing_time_seconds": round(
                (datetime.now() - start_time).total_seconds(), 2
            ),
        }

    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg error processing {filename}: {e.stderr or e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "file": filename,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        error_msg = f"Error processing {filename}: {e}"
        logging.error(error_msg)
        return {
            "success": False,
            "error": str(e),
            "file": filename,
            "timestamp": datetime.now().isoformat(),
        }

    finally:
        for file in [source, source_tmp]:
            try:
                if file.exists():
                    file.unlink()
            except Exception as cleanup_error:
                logging.warning(f"Error cleaning up file {file}: {cleanup_error}")


if __name__ == "__main__":
    print("=" * 60)
    print("Video Processing System")
    print("=" * 60)
    print(f"\nUnprocessed videos directory: {UNPROCESSED_DIR}")
    print(f"Processed videos directory: {PROCESSED_DIR}")
    print("\nAvailable functions:")
    print("  - process_video('filename.mp4')")
    print("\nTo use with Celery:")
    print("  - process_video.delay('filename.mp4')")
    print("=" * 60)
