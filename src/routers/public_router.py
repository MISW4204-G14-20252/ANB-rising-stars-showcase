from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from src.db.database import get_db
from src.models.db_models import Video, Usuario, Vote
from src.routers.auth_router import get_current_user
import src.schemas.pydantic_schemas as schemas

router = APIRouter(prefix="/api/public", tags=["Public"])

# Endpoint 7: Listar videos públicos disponibles
@router.get(
    "/videos",
    response_model=list[schemas.VideoPublicOut],
    summary="Lista de videos públicos disponibles para votación",
)
def list_public_videos(db: Session = Depends(get_db)):
    """
    Devuelve todos los videos que han sido publicados para votación.
    No requiere autenticación obligatoria.
    """
    videos = (
        db.query(Video)
        .filter(Video.status == "processed")
        .order_by(desc(Video.votes_count))
        .all()
    )

    if not videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay videos públicos disponibles.",
        )

    return videos


# Endpoint 8: Emitir un voto por un video público
@router.post(
    "/videos/{video_id}/vote",
    status_code=status.HTTP_200_OK,
    summary="Emite un voto por un video público (1 voto por usuario)",
)
def vote_public_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Permite que un usuario autenticado emita un voto por un video público.
    Solo se permite un voto por usuario por video.
    """
    video = db.query(Video).filter(Video.id == video_id, Video.status == "processed").first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El video con id={video_id} no existe o no es público.",
        )

    # Validar si el usuario ya votó este video
    existing_vote = (
        db.query(Vote)
        .filter(Vote.video_id == video_id, Vote.user_id == current_user.id)
        .first()
    )
    if existing_vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya has votado por este video.",
        )

    # Registrar el voto
    vote = Vote(video_id=video_id, user_id=current_user.id)
    db.add(vote)

    # Incrementar contador de votos
    video.votes_count = (video.votes_count or 0) + 1

    db.commit()
    db.refresh(video)

    return {
        "message": "Voto registrado correctamente.",
        "video_id": video.id,
        "total_votos": video.votes_count,
    }


# Endpoint 9: Mostrar ranking de jugadores por votos acumulados
@router.get(
    "/rankings",
    response_model=list[schemas.RankingOut],
    summary="Muestra el ranking actual de los jugadores por votos acumulados",
)
def get_rankings(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10,
):
    """
    Devuelve un ranking de los jugadores ordenados por el total de votos
    acumulados en todos sus videos públicos.
    Admite paginación mediante parámetros `skip` y `limit`.
    """
    rankings = (
        db.query(
            Usuario.first_name.label("jugador"),
            func.coalesce(func.sum(Video.votes_count), 0).label("votos_acumulados"),
        )
        .join(Video, Video.owner_id == Usuario.id)
        .filter(Video.status == "processed")
        .group_by(Usuario.id)  # Solo agrupar por ID (suficiente y más eficiente)
        .order_by(desc(func.coalesce(func.sum(Video.votes_count), 0)))
        .offset(skip)
        .limit(limit)
        .all()
    )

    if not rankings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay datos de ranking disponibles.",
        )

    return [
        {"jugador": r.jugador, "votos_acumulados": r.votos_acumulados}
        for r in rankings
    ]