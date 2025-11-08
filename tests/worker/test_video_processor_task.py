import pytest
import worker.video_processor_task as task
from types import SimpleNamespace
from pathlib import Path


# ---------------------------------------------------------
# 1️⃣ Verificar registro de tarea Celery
# ---------------------------------------------------------
def test_task_is_registered():
    """La tarea Celery 'process_video' debe estar definida"""
    assert hasattr(task, "process_video")
    assert callable(task.process_video)
    assert isinstance(task.celery.tasks, dict)


# ---------------------------------------------------------
# 2️⃣ Caso éxito: procesamiento simulado sin errores
# ---------------------------------------------------------
def test_process_video_success(monkeypatch, tmp_path):
    """Simula un procesamiento exitoso sin ejecutar ffmpeg"""

    # Creamos un archivo temporal simulando video sin fallos
    fake_file = tmp_path / "video1.mp4"
    fake_file.write_text("dummy video data")

    # Mock paths
    monkeypatch.setattr(task, "UNPROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "BASE_DIR", tmp_path)

    # Mock subprocess.run para que no llame ffmpeg real
    monkeypatch.setattr(task.subprocess, "run", lambda *a, **k: None)

    # Mock de DB: simulamos commit sin error
    fake_db = SimpleNamespace()
    fake_db.query = lambda model: fake_db
    fake_db.filter = lambda *a, **k: fake_db
    fake_db.update = lambda *a, **k: None
    fake_db.commit = lambda: None
    monkeypatch.setattr(task, "get_db", lambda: iter([fake_db]))

    video_data = {"id": 1, "filename": fake_file.name}
    result = task.process_video(video_data)

    assert result["success"] is True
    assert result["file"] == fake_file.name
    assert "processing_time_seconds" in result


# ---------------------------------------------------------
# 3️⃣ Caso error: archivo no encontrado
# ---------------------------------------------------------
def test_process_video_file_not_found(monkeypatch, tmp_path):
    """Debe retornar error si el archivo fuente no existe"""

    monkeypatch.setattr(task, "UNPROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "BASE_DIR", tmp_path)
    monkeypatch.setattr(task.subprocess, "run", lambda *a, **k: None)

    video_data = {"id": 5, "filename": "missing.mp4"}
    result = task.process_video(video_data)

    assert result["success"] is False
    assert "File not found" in result["error"]


# ---------------------------------------------------------
# 4️⃣ Caso error: falla de ffmpeg (subprocess.CalledProcessError)
# ---------------------------------------------------------
def test_process_video_ffmpeg_error(monkeypatch, tmp_path):
    """Debe manejar correctamente un error de ffmpeg"""

    fake_file = tmp_path / "bad.mp4"
    fake_file.write_text("bad data")

    class FakeError(Exception):
        stderr = b"ffmpeg failed"

    monkeypatch.setattr(task, "UNPROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "BASE_DIR", tmp_path)

    def raise_error(*a, **k):
        raise task.subprocess.CalledProcessError(1, "ffmpeg", stderr=b"ffmpeg error")

    monkeypatch.setattr(task.subprocess, "run", raise_error)

    fake_db = SimpleNamespace()
    fake_db.query = lambda model: fake_db
    fake_db.filter = lambda *a, **k: fake_db
    fake_db.update = lambda *a, **k: None
    fake_db.commit = lambda: None
    monkeypatch.setattr(task, "get_db", lambda: iter([fake_db]))

    result = task.process_video({"id": 10, "filename": fake_file.name})

    assert result["success"] is False
    assert "FFmpeg error" in result["error"]


# ---------------------------------------------------------
# 5️⃣ Caso error genérico inesperado
# ---------------------------------------------------------
def test_process_video_generic_error(monkeypatch, tmp_path):
    """Debe retornar error genérico si algo falla inesperadamente"""

    fake_file = tmp_path / "file.mp4"
    fake_file.write_text("test")

    monkeypatch.setattr(task, "UNPROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(task, "BASE_DIR", tmp_path)

    # Simulamos que subprocess.run lanza un error genérico
    def raise_generic(*a, **k):
        raise RuntimeError("Error genérico")

    monkeypatch.setattr(task.subprocess, "run", raise_generic)

    fake_db = SimpleNamespace()
    fake_db.query = lambda model: fake_db
    fake_db.filter = lambda *a, **k: fake_db
    fake_db.update = lambda *a, **k: None
    fake_db.commit = lambda: None
    monkeypatch.setattr(task, "get_db", lambda: iter([fake_db]))

    result = task.process_video({"id": 99, "filename": fake_file.name})

    assert result["success"] is False
    assert isinstance(result["error"], str)
    assert "Error" in result["error"]