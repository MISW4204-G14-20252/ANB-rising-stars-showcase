from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form
from sqlalchemy.orm import Session
import shutil, os
from src.db.database import get_db
from src.routers.auth_router import get_current_user
from src.models.db_models import Video, Usuario
import src.schemas.pydantic_schemas as schemas
from uuid import uuid4


router = APIRouter(prefix="/api/videos", tags=["Videos"])

UPLOAD_DIR = "src/uploads"
BASE_PROCESSED_URL = "http://localhost:8000/uploads/processed"
BASE_URL = "http://localhost:8000/uploads/processed"
PROCESSED_DIR = os.path.join(UPLOAD_DIR, "processed")
MAX_BYTES = 100 * 1024 * 1024

@router.post("/upload", status_code=201, summary="Video subido exitosamente, tarea creada.")
async def upload_video(
    title: str = Form(...),
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Validar tipo de archivo
    if not video_file.filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos MP4")

    # Validar tamaño (máx 100 MB)
    contents = await video_file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="El archivo excede el límite de 100 MB")
    await video_file.seek(0)

    # Validar duración (max 60 sgs)


    # Generar nombre único
    unique_name = f"{uuid4()}_{video_file.filename}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    # Registrar en BD con estado inicial
    new_video = Video(
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
    current_user: Usuario = Depends(get_current_user)
):
    videos = (
        db.query(Video)
        .filter(Video.owner_id == current_user.id)
        .order_by(Video.uploaded_at.desc())
        .all()
    )

    return videos

@router.get("/{video_id}", response_model=schemas.VideoOut, summary="Obtiene la informacion detallada de un video por ID")
def get_video_by_id(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Buscar el video
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El video con id={video_id} no existe."
        )

    # Verificar que pertenece al usuario actual
    if video.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a este video."
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
    "/{video_id}",
    status_code=status.HTTP_200_OK,
    summary="Elimina un video por ID"
)
def delete_video_by_id(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Buscar el video
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El video con id={video_id} no existe."
        )

    # Verificar que pertenece al usuario actual
    if video.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este video."
        )
    
    # Verificar que no esté procesado
    
    if video.status == "processed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El video ya esta procesado para votación."
        )

    # Eliminar archivo del sistema
    file_path = os.path.join(UPLOAD_DIR, video.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"No se pudo borrar el archivo físico: {e}")

    # Eliminar registro en base de datos
    db.delete(video)
    db.commit()

    return {"message": f"Video '{video.title}' eliminado correctamente.", "video_id": video_id}