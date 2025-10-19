import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture(scope="session")
def client():
    """Cliente de pruebas para los endpoints FastAPI"""
    return TestClient(app)


@pytest.fixture
def mock_video_data():
    """Datos falsos para crear o validar un video"""
    return {
        "id": 1,
        "title": "Video de prueba",
        "status": "uploaded",
        "filename": "test_video.mp4",
        "owner_id": 1,
        "uploaded_at": "2025-10-19T12:00:00",
        "processed_at": None,
        "processed_url": None,
    }