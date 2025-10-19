import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.routers import videos_router
import io
from fastapi import UploadFile

client = TestClient(app)


def test_get_videos_unauthorized():
    """Debe retornar 401 si no hay token"""
    response = client.get("/api/videos/")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_get_videos_authorized():
    """Debe retornar lista vacía si el usuario no tiene videos"""

    def fake_get_current_user():
        class User:
            id = 1
        return User()

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def order_by(self, *args, **kwargs): return self
        def all(self): return []

    # ✅ aquí usamos las referencias reales
    app.dependency_overrides[videos_router.get_current_user] = fake_get_current_user
    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()

    response = client.get(
        "/api/videos/",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code in (200, 204, 404)

    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "video_status,expected",
    [
        ("uploaded", 200),
        ("processed", 400),
    ],
)
def test_video_delete_behavior(video_status, expected):
    """Valida eliminación correcta o bloqueada según estado del video"""

    class FakeVideo:
        id = 1
        title = "Video Test"
        owner_id = 1
        status = video_status
        filename = "video.mp4"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeVideo()
        def delete(self, obj): ...
        def commit(self): ...

    def fake_user(): return type("U", (), {"id": 1})()

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    response = client.delete(
        "/api/videos/1",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == expected
    app.dependency_overrides.clear()


def test_video_delete_forbidden():
    """Debe retornar 403 si el video pertenece a otro usuario"""

    class FakeVideo:
        id = 1
        title = "Video ajeno"
        owner_id = 999
        status = "uploaded"
        filename = "video.mp4"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeVideo()

    def fake_user(): return type("U", (), {"id": 1})()

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    response = client.delete(
        "/api/videos/1",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 403
    assert "permiso" in response.json()["detail"].lower()
    app.dependency_overrides.clear()
    
def test_get_video_by_id_success():
    """Debe retornar el video si pertenece al usuario"""
    from src.routers import videos_router

    class FakeVideo:
        id = 1
        title = "Mi video"
        owner_id = 1
        status = "uploaded"
        uploaded_at = "2025-10-19T12:00:00"
        processed_at = None
        filename = "test.mp4"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeVideo()

    def fake_user(): return type("U", (), {"id": 1})()

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    client = TestClient(app)
    r = client.get("/api/videos/1", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200
    assert r.json()["title"] == "Mi video"
    app.dependency_overrides.clear()


def test_get_video_by_id_not_found():
    """Debe retornar 404 si el video no existe"""
    from src.routers import videos_router

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return None

    def fake_user(): return type("U", (), {"id": 1})()

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    r = client.get("/api/videos/999", headers={"Authorization": "Bearer token"})
    assert r.status_code == 404
    app.dependency_overrides.clear()


def test_get_video_by_id_forbidden():
    """Debe retornar 403 si el video pertenece a otro usuario"""
    from src.routers import videos_router

    class FakeVideo:
        id = 1
        title = "Otro video"
        owner_id = 999
        status = "uploaded"
        uploaded_at = "2025-10-19T12:00:00"
        processed_at = None
        filename = "test.mp4"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeVideo()

    def fake_user(): return type("U", (), {"id": 1})()

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    r = client.get("/api/videos/1", headers={"Authorization": "Bearer token"})
    assert r.status_code == 403
    app.dependency_overrides.clear()
    
    

def test_upload_video_invalid_format(monkeypatch):
    from src.routers import videos_router

    fake_user = lambda: type("U", (), {"id": 1})()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    # Simulamos get_db sin base real
    class FakeDB:
        def add(self, x): ...
        def commit(self): ...
        def refresh(self, x): ...
    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()

    video = UploadFile(filename="test.txt", file=io.BytesIO(b"1234"))
    data = {"title": "Test Video"}

    r = client.post(
        "/api/videos/upload",
        files={"video_file": (video.filename, video.file, "text/plain")},
        data=data,
        headers={"Authorization": "Bearer token"},
    )
    assert r.status_code == 400
    assert "MP4" in r.json()["detail"]
    app.dependency_overrides.clear()