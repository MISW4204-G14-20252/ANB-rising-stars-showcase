import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.routers import public_router


client = TestClient(app)


# ---------------------------------------------------------
# 1️⃣ GET /api/public/videos
# ---------------------------------------------------------
def test_list_public_videos_success():
    """Debe devolver la lista de videos públicos procesados"""
    class FakeVideo:
        id = 1
        title = "Video 1"
        status = "processed"
        votes_count = 5
        owner_id = 1
        filename = "v1.mp4"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def all(self): return [FakeVideo()]

    app.dependency_overrides[public_router.get_db] = lambda: FakeDB()

    r = client.get("/api/public/videos")
    assert r.status_code == 200

    body = r.json()
    assert isinstance(body, list)
    assert body[0]["title"] == "Video 1"
    assert body[0]["votes_count"] == 5

    app.dependency_overrides.clear()


def test_list_public_videos_empty():
    """Debe retornar 404 si no hay videos públicos disponibles"""
    class FakeDB:
        def query(self, model): return self
        def filter(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def all(self): return []

    app.dependency_overrides[public_router.get_db] = lambda: FakeDB()

    r = client.get("/api/public/videos")
    assert r.status_code == 404
    assert "no hay" in r.json()["detail"].lower()

    app.dependency_overrides.clear()


# ---------------------------------------------------------
# 2️⃣ POST /api/public/videos/{video_id}/vote
# ---------------------------------------------------------
def test_vote_public_video_success():
    """Debe registrar voto exitosamente y aumentar contador"""

    class FakeVideo:
        id = 1
        status = "processed"
        votes_count = 2
        owner_id = 1

    class FakeDB:
        def query(self, model):
            self.model = model
            return self
        def filter(self, *a, **k): return self
        def first(self):
            # Si estamos buscando un voto, retornamos None (no ha votado)
            if self.model == public_router.Vote:
                return None
            # Si estamos buscando un video, retornamos el FakeVideo
            return FakeVideo()
        def add(self, obj): setattr(obj, "added", True)
        def commit(self): self.committed = True
        def refresh(self, obj): pass

    class FakeUser:
        id = 99

    app.dependency_overrides[public_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[public_router.get_current_user] = lambda: FakeUser()

    r = client.post("/api/public/videos/1/vote", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200

    body = r.json()
    assert body["message"].startswith("Voto registrado")
    assert body["total_votos"] == 3  # ✅ votos_count incrementado correctamente

    app.dependency_overrides.clear()


def test_vote_public_video_not_found():
    """Debe retornar 404 si el video no existe o no está procesado"""

    class FakeDB:
        def query(self, model): return self
        def filter(self, *a, **k): return self
        def first(self): return None

    app.dependency_overrides[public_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[public_router.get_current_user] = lambda: type("U", (), {"id": 1})()

    r = client.post("/api/public/videos/999/vote", headers={"Authorization": "Bearer token"})
    assert r.status_code == 404
    assert "no existe" in r.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_vote_public_video_already_voted():
    """Debe retornar 400 si el usuario ya votó por el video"""

    class FakeVideo:
        id = 1
        status = "processed"
        votes_count = 10
        owner_id = 1

    class FakeVote:
        video_id = 1
        user_id = 1

    class FakeDB:
        def __init__(self): self.query_called = 0
        def query(self, model):
            self.query_called += 1
            self.model = model
            return self
        def filter(self, *a, **k): return self
        def first(self):
            # 1ra llamada -> video, 2da llamada -> voto existente
            return FakeVideo() if self.query_called == 1 else FakeVote()

    app.dependency_overrides[public_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[public_router.get_current_user] = lambda: type("U", (), {"id": 1})()

    r = client.post("/api/public/videos/1/vote", headers={"Authorization": "Bearer token"})
    assert r.status_code == 400
    assert "ya has votado" in r.json()["detail"].lower()

    app.dependency_overrides.clear()


# ---------------------------------------------------------
# 3️⃣ GET /api/public/rankings
# ---------------------------------------------------------
def test_get_rankings_success():
    """Debe devolver el ranking con jugadores"""
    class FakeRow:
        jugador = "Leo"
        votos_acumulados = 15

    class FakeDB:
        def query(self, *a, **k): return self
        def join(self, *a, **k): return self
        def filter(self, *a, **k): return self
        def group_by(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def offset(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def all(self): return [FakeRow()]

    app.dependency_overrides[public_router.get_db] = lambda: FakeDB()

    r = client.get("/api/public/rankings")
    assert r.status_code == 200
    assert r.json()[0]["jugador"] == "Leo"
    assert "votos_acumulados" in r.json()[0]

    app.dependency_overrides.clear()


def test_get_rankings_empty():
    """Debe retornar 404 si no hay datos en el ranking"""
    class FakeDB:
        def query(self, *a, **k): return self
        def join(self, *a, **k): return self
        def filter(self, *a, **k): return self
        def group_by(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def offset(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def all(self): return []

    app.dependency_overrides[public_router.get_db] = lambda: FakeDB()

    r = client.get("/api/public/rankings")
    assert r.status_code == 404
    assert "ranking" in r.json()["detail"].lower()

    app.dependency_overrides.clear()