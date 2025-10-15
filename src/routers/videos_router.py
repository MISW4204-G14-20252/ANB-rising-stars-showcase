from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
import shutil, os
from src.db.database import get_db
from src.routers.auth_router import get_current_user
import src.models as models
import src.schemas.pydantic_schemas as schemas
from uuid import uuid4


router = APIRouter(prefix="/api/videos", tags=["Videos"])

UPLOAD_DIR = "src/uploads"
BASE_PROCESSED_URL = "http://localhost:8000/uploads/processed"
BASE_URL = "http://localhost:8000/uploads/processed"
PROCESSED_DIR = os.path.join(UPLOAD_DIR, "processed")

@router.post("/upload", status_code=201, summary="Video subido exitosamente, tarea creada.")
async def upload_video(
    title: str,
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    # Validar tipo de archivo
    if not video_file.filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos MP4")

    # Validar tamaño (máx 100 MB)
    contents = await video_file.read()
    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 100 MB")
    await video_file.seek(0)

    # Generar nombre único
    unique_name = f"{uuid4()}_{video_file.filename}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    # Registrar en BD con estado inicial
    new_video = models.Video(
        title=title,
        filename=unique_name,
        owner_id=current_user.id
    )
    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    """
    # Encolar tarea asíncrona (procesamiento)
    try:
        from src.tasks import process_video_task
        process_video_task.delay(new_video.id, file_path)
    except Exception as e:
        print(f" Error encolando tarea: {e}")
    """

    return {"message": "Video subido correctamente. Procesamiento en curso.", "task_id": new_video.id}



@router.get("/", response_model=list[schemas.VideoOut], summary="Lista de videos subidos por el usuario autenticado")
def list_my_videos(
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    videos = db.query(models.Video).filter(models.Video.owner_id == current_user.id).order_by(models.Video.uploaded_at.desc()).all()

    response = []
    for video in videos:
        video_data = {
            "video_id": video.id,
            "title": video.title,
            "status": video.status,
            "uploaded_at": video.uploaded_at,
            "processed_at": video.processed_at,
        }
        if video.status == "processed":
            video_data["processed_url"] = f"{BASE_URL}/{video.filename}"
        response.append(video_data)

    return response



@router.get(
    "/{video_id}",
    response_model=schemas.VideoDetailOut,
    summary="Detalle de un video específico"
)
def get_video_detail(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Si existe pero no pertenece al usuario autenticado
    if video.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a este video")

    # Construir URLs
    original_url = f"{BASE_UPLOAD_URL}/{video.filename}"
    processed_url = None
    if video.status == "processed":
        processed_url = f"{BASE_PROCESSED_URL}/{video.filename}"

    # (Simulación, si aún no tienes sistema de votos)
    votes = getattr(video, "votes", 0)

    return {
        "video_id": video.id,
        "title": video.title,
        "status": video.status,
        "uploaded_at": video.uploaded_at,
        "processed_at": video.processed_at,
        "original_url": original_url,
        "processed_url": processed_url,
        "votes": votes
    }


@router.delete(
    "/{video_id}",
    summary="Elimina un video subido por el usuario autenticado"
)
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    # Buscar video
    video = db.query(models.Video).filter(models.Video.id == video_id).first()

    # Si no existe → 404
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Si existe pero no pertenece al usuario → 403
    if video.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este video")

    # Si el video ya fue procesado → 400
    # (o en el futuro, si tuviera campo "published_for_voting", también se validaría aquí)
    if video.status == "processed":
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar un video ya procesado o publicado para votación"
        )

    # Intentar eliminar archivo original y procesado
    original_path = os.path.join(BASE_UPLOAD_DIR, video.filename)
    processed_path = os.path.join(PROCESSED_DIR, video.filename)

    for path in [original_path, processed_path]:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    # Eliminar registro en BD
    db.delete(video)
    db.commit()

    return {
        "message": "El video ha sido eliminado exitosamente.",
        "video_id": video.id
    }