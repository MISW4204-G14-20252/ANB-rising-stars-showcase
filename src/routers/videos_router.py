from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form
from sqlalchemy.orm import Session
import shutil
import os
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

router = APIRouter(prefix="/api/videos", tags=["Videos"])

BASE_DIR = Path(__file__).parent.parent.parent

BASE_PROCESSED_URL = "http://localhost:8000/uploads/processed"
BASE_URL = "http://localhost:8000/uploads/processed"
UPLOAD_DIR = BASE_DIR / "videos/unprocessed-videos"
PROCESSED_DIR = BASE_DIR / "videos/processed-videos"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

logger.addHandler(console_handler)

MAX_BYTES = 100 * 1024 * 1024
MIN_T, MAX_T = 20, 60


def _video_info(p: Path):
    info = MediaInfo.parse(p)
    for t in info.tracks:
        if t.track_type == "Video" and t.duration:
            duration = float(t.duration) / 1000.0
            width = int(t.width or 0)
            height = int(t.height or 0)
            return duration, width, height
    return 0.0, 0, 0


@router.post(
    "/upload", status_code=201, summary="Video subido exitosamente, tarea creada."
)
async def upload_video(
    title: str = Form(...),
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Validar tipo de archivo
    logging.info(f"Uploading file: {video_file.filename}")
    if not video_file.filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos MP4")

    # Validar tamaño (máx 100 MB)
    contents = await video_file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(
            status_code=400, detail="El archivo excede el límite de 100 MB"
        )
    await video_file.seek(0)

    # Generar nombre único y seguro (no usar el filename del usuario directamente)
    # Extraer y validar extensión
    ext = Path(video_file.filename).suffix.lower()
    if ext != ".mp4":
        raise HTTPException(status_code=400, detail="Solo se permiten archivos MP4")

    # Nombre seguro: UUID.hex + extensión
    unique_name = f"{uuid4().hex}{ext}"

    # Asegurar directorio de subida
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / unique_name

    # Guardar archivo de forma segura (async)
    # ya leímos el contenido para validar tamaño, reutilizamos 'contents'
    try:
        async with aiofiles.open(file_path, "wb") as out_f:
            await out_f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando el archivo: {e}")

    # Validar duración (min 20sgs max 60 sgs)
    dur, width, height = _video_info(Path(file_path))

    if dur <= 0.0:
        try:
            file_path.unlink()
        except Exception:
            pass
        raise HTTPException(
            status_code=400, detail="No se pudo determinar la duración del video."
        )

    if not (MIN_T <= dur <= MAX_T):
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail=f"Duración inválida: {dur:.1f}s (debe estar entre {MIN_T} y {MAX_T} segundos).",
        )

    # Validar resolución: 1080p o superior
    if height < 1080 and width < 1920:
        try:
            file_path.unlink()
        except Exception:
            pass
        raise HTTPException(
            status_code=400,
            detail=f"Resolución demasiado baja: {width}x{height} (mínimo 1920x1080).",
        )

    # Registrar en BD con estado inicial
    new_video = Video(title=title, filename=unique_name, owner_id=current_user.id)
    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    # Encolar tarea asíncrona (procesamiento)
    try:
        from worker.video_processor_task import process_video

        process_video.delay(new_video.to_dict())
    except Exception as e:
        print(f" Error encolando tarea: {e}")

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
    db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)
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
    summary="Obtiene la informacion detallada de un video por ID",
)
def get_video_by_id(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Buscar el video
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El video con id={video_id} no existe.",
        )

    # Verificar que pertenece al usuario actual
    if video.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a este video.",
        )

    # Respuesta
    response = {
        "id": video.id,
        "title": video.title,
        "status": video.status,
        "uploaded_at": video.uploaded_at,
        "processed_at": video.processed_at,
        "filename": video.filename,
    }

    # Si ya fue procesado, incluir la URL
    if video.status == "processed":
        response["processed_url"] = f"{BASE_URL}/{video.filename}"
    else:
        response["processed_url"] = None

    return response


@router.delete(
    "/{video_id}", status_code=status.HTTP_200_OK, summary="Elimina un video por ID"
)
def delete_video_by_id(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Buscar el video
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El video con id={video_id} no existe.",
        )

    # Verificar que pertenece al usuario actual
    if video.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este video.",
        )

    # Verificar que no esté procesado
    if video.status == "processed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El video ya esta procesado para votación.",
        )

    # Eliminar archivo del sistema
    file_path = UPLOAD_DIR / video.filename
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            print(f"No se pudo borrar el archivo físico: {e}")

    # Eliminar registro en base de datos
    db.delete(video)
    db.commit()

    return {
        "message": f"Video '{video.title}' eliminado correctamente.",
        "video_id": video_id,
    }
