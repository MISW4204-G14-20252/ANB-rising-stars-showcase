from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form
from sqlalchemy.orm import Session
import logging
from src.db.database import get_db
from src.routers.auth_router import get_current_user
from src.models.db_models import Video, Usuario
import src.schemas.pydantic_schemas as schemas
from uuid import uuid4
import aiofiles
from pymediainfo import MediaInfo
from pathlib import Path
import sys
import os

# 🔹 Import utilidades centralizadas para S3
from src.utils.s3_utils import upload_to_s3, delete_from_s3, BUCKET_NAME

router = APIRouter(prefix="/api/videos", tags=["Videos"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

MAX_BYTES = 100 * 1024 * 1024
MIN_T, MAX_T = 20, 60

# Región y URL base para construir los links públicos
S3_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BASE_URL = f"https://{BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com"


# =======================================================
# FUNCIONES AUXILIARES
# =======================================================
def _video_info(p: Path):
    """Extrae duración, ancho y alto de un archivo de video."""
    info = MediaInfo.parse(p)
    for t in info.tracks:
        if t.track_type == "Video" and t.duration:
            duration = float(t.duration) / 1000.0
            width = int(t.width or 0)
            height = int(t.height or 0)
            return duration, width, height
    return 0.0, 0, 0


# =======================================================
# ENDPOINTS
# =======================================================

@router.post(
    "/upload",
    status_code=201,
    summary="Sube un video y encola la tarea de procesamiento.",
)
async def upload_video(
    title: str = Form(...),
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    logger.info(f"Subiendo archivo: {video_file.filename}")

    # Validar extensión
    ext = Path(video_file.filename).suffix.lower()
    if ext != ".mp4":
        raise HTTPException(status_code=400, detail="Solo se permiten archivos MP4")

    # Validar tamaño máximo
    contents = await video_file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 100 MB")
    await video_file.seek(0)

    # Crear nombre único temporal
    unique_name = f"{uuid4().hex}{ext}"
    temp_path = Path(f"videos/unprocessed-videos/{unique_name}")

    # Guardar temporalmente para validación
    try:
        async with aiofiles.open(temp_path, "wb") as out_f:
            await out_f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando archivo temporal: {e}")

    # Validar metadatos
    dur, width, height = _video_info(temp_path)
    if dur <= 0.0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="No se pudo determinar la duración del video.")
    if not (MIN_T <= dur <= MAX_T):
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Duración inválida: {dur:.1f}s (debe estar entre {MIN_T}-{MAX_T}s).",
        )
    if height < 1080 and width < 1920:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Resolución demasiado baja: {width}x{height} (mínimo 1920x1080).",
        )

    # Subir archivo validado a S3
    s3_key = f"unprocessed-videos/{unique_name}"
    success = upload_to_s3(temp_path, s3_key)
    temp_path.unlink(missing_ok=True)
    if not success:
        raise HTTPException(status_code=500, detail="Error subiendo archivo a S3")

    # Registrar en BD con estado inicial
    new_video = Video(title=title, filename=s3_key, owner_id=current_user.id)
    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    # Encolar tarea Celery
    try:
        from worker.video_processor_task import process_video
        process_video.delay(new_video.to_dict())
    except Exception as e:
        logger.error(f"Error encolando tarea Celery: {e}")

    return {
        "message": "Video subido correctamente. Procesamiento en curso.",
        "task_id": new_video.id,
    }


@router.get(
    "/",
    response_model=list[schemas.VideoOut],
    summary="Lista de videos subidos por el usuario autenticado",
)
def list_my_videos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    videos = (
        db.query(Video)
        .filter(Video.owner_id == current_user.id)
        .order_by(Video.uploaded_at.desc())
        .all()
    )
    return videos


@router.get(
    "/{video_id}",
    response_model=schemas.VideoOut,
    summary="Obtiene la información detallada de un video por ID",
)
def get_video_by_id(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail=f"El video con id={video_id} no existe.")

    if video.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a este video.")

    response = {
        "id": video.id,
        "title": video.title,
        "status": video.status,
        "uploaded_at": video.uploaded_at,
        "processed_at": video.processed_at,
        "filename": video.filename,
    }

    # Generar URL pública si ya está procesado
    if video.status == "processed":
        response["processed_url"] = f"{S3_BASE_URL}/{video.filename}"
    else:
        response["processed_url"] = None

    return response


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_200_OK,
    summary="Elimina un video por ID",
)
def delete_video_by_id(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"El video con id={video_id} no existe.")

    if video.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este video.")

    if video.status == "processed":
        raise HTTPException(status_code=400, detail="El video ya está procesado para votación.")

    # Eliminar del bucket S3
    delete_from_s3(video.filename)

    # Eliminar registro en BD
    db.delete(video)
    db.commit()

    return {"message": f"Video '{video.title}' eliminado correctamente.", "video_id": video_id}