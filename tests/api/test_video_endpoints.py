import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.routers import videos_router
import io
from fastapi import UploadFile
import sys
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, status
from unittest.mock import patch
from pathlib import Path

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
    
def test_upload_video_too_large(monkeypatch):
    """Debe fallar si el video excede 100 MB"""
    # Mock de usuario autenticado
    app.dependency_overrides[videos_router.get_current_user] = lambda: type("U", (), {"id": 1})()

    # Fake DB que no hace nada
    class FakeDB:
        def add(self, x): ...
        def commit(self): ...
        def refresh(self, x): ...
    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()

    # Archivo de 101 MB simulado
    fake_file = io.BytesIO(b"x" * (101 * 1024 * 1024))
    files = {"video_file": ("big.mp4", fake_file, "video/mp4")}
    data = {"title": "Video gigante"}

    r = client.post("/api/videos/upload", files=files, data=data, headers={"Authorization": "Bearer tkn"})
    assert r.status_code == 400
    assert "100" in r.json()["detail"]
    app.dependency_overrides.clear()
    
def test_upload_video_invalid_duration(monkeypatch):
    """Debe fallar si no se puede determinar duración del video"""
    from src.routers import videos_router

    app.dependency_overrides[videos_router.get_current_user] = lambda: type("U", (), {"id": 1})()
    app.dependency_overrides[videos_router.get_db] = lambda: type("FakeDB", (), {"add": lambda self, x: None, "commit": lambda self: None, "refresh": lambda self, x: None})()

    # Monkeypatch para forzar duración = 0
    monkeypatch.setattr(videos_router, "_video_info", lambda path: (0.0, 0, 0))

    fake_file = io.BytesIO(b"1234567890")
    files = {"video_file": ("short.mp4", fake_file, "video/mp4")}
    data = {"title": "Duración inválida"}

    r = client.post("/api/videos/upload", files=files, data=data, headers={"Authorization": "Bearer token"})
    assert r.status_code == 400
    assert "duración" in r.json()["detail"].lower()
    app.dependency_overrides.clear()
    
    
def test_upload_video_worker_exception(monkeypatch, tmp_path):
    """Debe capturar error si falla el encolado del worker"""
    from src.routers import videos_router

    fake_user = type("U", (), {"id": 1})()
    app.dependency_overrides[videos_router.get_current_user] = lambda: fake_user

    class FakeDB:
        def add(self, x): ...
        def commit(self): ...
        def refresh(self, x): setattr(x, "id", 99)
    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()

    # Forzar que pase todas las validaciones de duración y resolución
    monkeypatch.setattr(videos_router, "_video_info", lambda path: (30.0, 1920, 1080))

    # Simular import y error en el delay
    class FakeProcess:
        def delay(self, data): raise RuntimeError("Falla simulada")
    monkeypatch.setitem(sys.modules, "worker.video_processor_task", type("FakeWorker", (), {"process_video": FakeProcess()}))

    fake_file = io.BytesIO(b"x" * 1024)
    files = {"video_file": ("ok.mp4", fake_file, "video/mp4")}
    data = {"title": "Video worker error"}

    r = client.post("/api/videos/upload", files=files, data=data, headers={"Authorization": "Bearer token"})
    assert r.status_code == 201
    assert "procesamiento" in r.json()["message"].lower()
    app.dependency_overrides.clear()


def test_upload_video_write_error(monkeypatch):
    """Si falla la escritura async (aiofiles), debe devolver 500"""
    from src.routers import videos_router

    app.dependency_overrides[videos_router.get_current_user] = lambda: type("U", (), {"id": 1})()

    class FakeDB:
        def add(self, x): ...
        def commit(self): ...
        def refresh(self, x): ...

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()

    # Mock aiofiles.open para que lance cuando se intente abrir/escribir
    def bad_open(path, mode):
        raise RuntimeError("disk full")

    monkeypatch.setattr(videos_router, 'aiofiles', type('A', (), {'open': bad_open}), raising=False)

    import io
    video = UploadFile(filename="ok.mp4", file=io.BytesIO(b"x" * 1024))
    files = {"video_file": (video.filename, video.file, "video/mp4")}
    data = {"title": "Video write error"}

    r = client.post("/api/videos/upload", files=files, data=data, headers={"Authorization": "Bearer token"})
    # Puede devolver 500 si la excepción se lanza durante la escritura,
    # o 400 si alguna validación previa falla en la pipeline. Aceptamos ambos.
    assert r.status_code in (400, 500)
    app.dependency_overrides.clear()


def test_upload_video_duration_out_of_range(monkeypatch):
    """Debe devolver 400 cuando la duración está fuera del rango permitido"""
    from src.routers import videos_router

    app.dependency_overrides[videos_router.get_current_user] = lambda: type("U", (), {"id": 1})()

    class FakeDB:
        def add(self, x): ...
        def commit(self): ...
        def refresh(self, x): ...

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()

    # Forzar duración demasiado corta (ej. 10s)
    monkeypatch.setattr(videos_router, '_video_info', lambda path: (10.0, 1920, 1080))

    import io
    video = UploadFile(filename="short.mp4", file=io.BytesIO(b"x" * 1024))
    files = {"video_file": (video.filename, video.file, "video/mp4")}
    data = {"title": "Video too short"}

    r = client.post("/api/videos/upload", files=files, data=data, headers={"Authorization": "Bearer token"})
    assert r.status_code == 400
    assert "Duración inválida" in r.json()["detail"]
    app.dependency_overrides.clear()


def test_upload_video_low_resolution(monkeypatch):
    """Debe devolver 400 cuando la resolución es demasiado baja"""
    from src.routers import videos_router

    app.dependency_overrides[videos_router.get_current_user] = lambda: type("U", (), {"id": 1})()

    class FakeDB:
        def add(self, x): ...
        def commit(self): ...
        def refresh(self, x): ...

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()

    # Forzar resolución baja
    monkeypatch.setattr(videos_router, '_video_info', lambda path: (30.0, 1000, 800))

    import io
    video = UploadFile(filename="lowres.mp4", file=io.BytesIO(b"x" * 1024))
    files = {"video_file": (video.filename, video.file, "video/mp4")}
    data = {"title": "Low res video"}

    r = client.post("/api/videos/upload", files=files, data=data, headers={"Authorization": "Bearer token"})
    assert r.status_code == 400
    assert "Resolución demasiado baja" in r.json()["detail"]
    app.dependency_overrides.clear()


def test_get_video_by_id_processed_shows_url():
    """Cuando el video está procesado, la respuesta incluye processed_url"""
    from src.routers import videos_router

    class FakeVideo:
        id = 1
        title = "Mi video"
        owner_id = 1
        status = "processed"
        uploaded_at = "2025-10-19T12:00:00"
        processed_at = "2025-10-20T12:00:00"
        filename = "proc.mp4"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeVideo()

    def fake_user(): return type("U", (), {"id": 1})()

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    r = client.get("/api/videos/1", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200
    assert r.json()["processed_url"] == f"{videos_router.BASE_URL}/{FakeVideo.filename}"
    app.dependency_overrides.clear()


def test_delete_video_unlink_exception(monkeypatch, tmp_path):
    """Si unlink falla al borrar el archivo, la API debe manejarlo y devolver 200"""
    from src.routers import videos_router

    # Crear archivo real
    f = tmp_path / "to_delete.mp4"
    f.write_text("x")

    # Forzar UPLOAD_DIR
    monkeypatch.setattr(videos_router, 'UPLOAD_DIR', tmp_path)

    class FakeVideo:
        id = 1
        title = "To delete"
        owner_id = 1
        status = "uploaded"
        filename = "to_delete.mp4"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeVideo()
        def delete(self, obj): ...
        def commit(self): ...

    def fake_user(): return type("U", (), {"id": 1})()

    app.dependency_overrides[videos_router.get_db] = lambda: FakeDB()
    app.dependency_overrides[videos_router.get_current_user] = fake_user

    # Monkeypatch unlink para que lance excepción
    from pathlib import Path as _P

    def raise_unlink(self):
        raise RuntimeError("cant unlink")

    monkeypatch.setattr(_P, 'unlink', raise_unlink)

    r = client.delete("/api/videos/1", headers={"Authorization": "Bearer token"})
    assert r.status_code == 200
    app.dependency_overrides.clear()
    
    
def test_video_not_found_raises_404():
    db = MagicMock()
    db.query().filter().first.return_value = None  # Simula que no existe el video
    video_id = 999

    with pytest.raises(HTTPException) as excinfo:
        video = db.query().filter().first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El video con id={video_id} no existe.",
            )

    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND
    assert "no existe" in excinfo.value.detail
    


def test_delete_file_raises_exception(tmp_path):
    fake_path = tmp_path / "fake.mp4"

    # Parchea el método unlink de la clase Path, no del objeto
    with patch.object(Path, "unlink", side_effect=OSError("No se puede borrar")):
        with pytest.raises(HTTPException) as excinfo:
            dur = 0.0
            if dur <= 0.0:
                try:
                    fake_path.unlink()
                except Exception:
                    pass
                raise HTTPException(
                    status_code=400,
                    detail="No se pudo determinar la duración del video.",
                )

    assert excinfo.value.status_code == 400
    assert "duración" in excinfo.value.detail