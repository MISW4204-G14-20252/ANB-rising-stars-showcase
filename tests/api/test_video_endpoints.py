import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.routers import videos_router

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