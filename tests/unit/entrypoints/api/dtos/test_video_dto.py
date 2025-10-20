from src.schemas.pydantic_schemas import VideoOut

def test_video_dto_structure(mock_video_data):
    """Valida que el DTO de video tenga los atributos esperados"""
    # Elimina owner_id del mock si ya no existe en el modelo
    mock_video_data.pop("owner_id", None)

    video = VideoOut(**mock_video_data)

    # Aserciones según el modelo actual
    assert video.title == "Video de prueba"
    assert video.status in ["uploaded", "processed"]
    assert video.filename.endswith(".mp4")
    assert video.id == 1
    assert hasattr(video, "processed_url")
    assert hasattr(video, "uploaded_at")