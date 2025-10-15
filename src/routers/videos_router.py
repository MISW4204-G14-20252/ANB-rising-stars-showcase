from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
import shutil, os
from src.db.database import get_db
from src.routers.auth_router import get_current_user
import src.models as models
import src.schemas.pydantic_schemas as schemas


router = APIRouter(prefix="/api/videos", tags=["Videos"])

UPLOAD_DIR = "src/uploads"

@router.post("/upload", status_code=201)
async def upload_video(
    title: str,
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    # Validar tipo de archivo
    if not video_file.filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos MP4")

    # Guardar archivo en disco
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, video_file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    # Registrar en base de datos
    new_video = models.Video(
        title=title,
        filename=video_file.filename,
        owner_id=current_user.id
    )
    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    return {"message": "Video subido correctamente. Procesamiento en curso", "task_id": new_video.id}



@router.get("/", response_model=list[schemas.VideoOut])
def list_my_videos(
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    videos = db.query(models.Video).filter(models.Video.owner_id == current_user.id).all()
    return videos



@router.get("/{video_id}", response_model=schemas.VideoOut)
def get_video_detail(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    video = db.query(models.Video).filter(
        models.Video.id == video_id,
        models.Video.owner_id == current_user.id
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    return video


@router.get("/{video_id}", response_model=schemas.VideoOut)
def get_video_detail(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    video = db.query(models.Video).filter(
        models.Video.id == video_id,
        models.Video.owner_id == current_user.id
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    return video


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.db_models.Usuario = Depends(get_current_user)
):
    video = db.query(models.Video).filter(
        models.Video.id == video_id,
        models.Video.owner_id == current_user.id
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")

    if video.status == "processed":
        raise HTTPException(status_code=400, detail="No se puede eliminar un video ya procesado")

    # Eliminar archivo físico
    try:
        os.remove(os.path.join(UPLOAD_DIR, video.filename))
    except FileNotFoundError:
        pass

    db.delete(video)
    db.commit()
    return {"message": "Video eliminado exitosamente"}