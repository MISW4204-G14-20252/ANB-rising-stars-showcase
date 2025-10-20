import pytest
from fastapi.testclient import TestClient
from jose import jwt
from src.main import app
from src.routers import auth_router

client = TestClient(app)
SECRET_KEY = auth_router.SECRET_KEY
ALGORITHM = auth_router.ALGORITHM


# ---------------------------------------------------------------------
# 1️⃣ SIGNUP – Contraseñas diferentes
# ---------------------------------------------------------------------
def test_signup_password_mismatch():
    """Debe fallar si las contraseñas no coinciden"""
    data = {
        "first_name": "Leo",
        "last_name": "Rangel",
        "email": "test@uniandes.edu.co",
        "password1": "abc123",
        "password2": "xyz123",
        "city": "Bogotá",
        "country": "Colombia",
    }
    r = client.post("/api/auth/signup", json=data)
    assert r.status_code == 400
    assert "contraseñas" in r.json()["detail"].lower()


# ---------------------------------------------------------------------
# 2️⃣ SIGNUP – Email duplicado
# ---------------------------------------------------------------------
def test_signup_duplicate_email():
    """Debe fallar si el correo ya existe"""

    class FakeUser:
        email = "test@uniandes.edu.co"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeUser()

    # override dependency properly
    app.dependency_overrides[auth_router.get_db] = lambda: FakeDB()

    data = {
        "first_name": "Leo",
        "last_name": "Rangel",
        "email": "test@uniandes.edu.co",
        "password1": "abc123",
        "password2": "abc123",
        "city": "Bogotá",
        "country": "Colombia",
    }
    r = client.post("/api/auth/signup", json=data)

    # clean override
    app.dependency_overrides.clear()

    assert r.status_code == 400
    assert "correo" in r.json()["detail"].lower()


# ---------------------------------------------------------------------
# 3️⃣ LOGIN – Usuario no encontrado
# ---------------------------------------------------------------------
def test_login_user_not_found():
    """Debe fallar si el usuario no existe"""

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return None

    app.dependency_overrides[auth_router.get_db] = lambda: FakeDB()

    data = {"email": "no@existe.com", "password": "1234"}
    r = client.post("/api/auth/login", json=data)

    app.dependency_overrides.clear()

    assert r.status_code == 400
    assert "usuario no es correcto" in r.json()["detail"].lower()


# ---------------------------------------------------------------------
# 4️⃣ LOGIN – Contraseña incorrecta
# ---------------------------------------------------------------------
def test_login_wrong_password():
    """Debe fallar si la contraseña es incorrecta"""

    class FakeUser:
        email = "user@correo.com"
        password = "abc123"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeUser()

    app.dependency_overrides[auth_router.get_db] = lambda: FakeDB()

    data = {"email": "user@correo.com", "password": "zzz999"}
    r = client.post("/api/auth/login", json=data)

    app.dependency_overrides.clear()

    assert r.status_code == 400
    assert "contraseña" in r.json()["detail"].lower()


# ---------------------------------------------------------------------
# 5️⃣ LOGIN – Éxito
# ---------------------------------------------------------------------
def test_login_success():
    """Debe devolver un token si las credenciales son correctas"""

    class FakeUser:
        email = "user@correo.com"
        password = "abc123"

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return FakeUser()

    app.dependency_overrides[auth_router.get_db] = lambda: FakeDB()

    data = {"email": "user@correo.com", "password": "abc123"}
    r = client.post("/api/auth/login", json=data)

    app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    payload = jwt.decode(body["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "user@correo.com"


# ---------------------------------------------------------------------
# 6️⃣ verify_token – Token inválido
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_verify_token_invalid():
    """Debe lanzar 401 si el token es inválido"""
    from fastapi import HTTPException
    from src.routers.auth_router import verify_token

    with pytest.raises(HTTPException) as excinfo:
        await verify_token("token-falso")
    assert excinfo.value.status_code == 401


# ---------------------------------------------------------------------
# 7️⃣ get_current_user – Usuario no existe
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_current_user_not_found(monkeypatch):
    """Debe lanzar 401 si el usuario no existe"""
    from src.routers.auth_router import get_current_user

    fake_token = jwt.encode({"sub": "no@existe.com"}, SECRET_KEY, algorithm=ALGORITHM)

    class FakeDB:
        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return None

    monkeypatch.setattr("src.routers.auth_router.get_db", lambda: FakeDB())

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(fake_token, FakeDB())
    assert excinfo.value.status_code == 401
    
    # ---------------------------------------------------------------------
# 8️⃣ SIGNUP – Éxito (usuario nuevo)
# ---------------------------------------------------------------------
def test_signup_success(monkeypatch):
    """Debe crear el usuario correctamente y devolver 201"""

    class FakeDB:
        """Simula base de datos sin usuarios previos"""
        def __init__(self):
            self.committed = False
            self.user_created = None

        def query(self, model): return self
        def filter(self, *args, **kwargs): return self
        def first(self): return None  # No existe usuario
        def add(self, obj):
            obj.id = 1  # ← FIX: id simulado para el schema
            self.user_created = obj
        def commit(self): self.committed = True
        def refresh(self, obj): pass

    db = FakeDB()
    app.dependency_overrides[auth_router.get_db] = lambda: db

    data = {
        "first_name": "Leo",
        "last_name": "Rangel",
        "email": "nuevo@uniandes.edu.co",
        "password1": "abc123",
        "password2": "abc123",
        "city": "Bogotá",
        "country": "Colombia",
    }

    r = client.post("/api/auth/signup", json=data)

    app.dependency_overrides.clear()

    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "nuevo@uniandes.edu.co"
    assert body["id"] == 1
    assert db.committed is True
    assert db.user_created.email == "nuevo@uniandes.edu.co"

# ---------------------------------------------------------------------
# 9️⃣ verify_token – Token válido
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_verify_token_valid(monkeypatch):
    """Debe devolver el username (correo) si el token es válido"""
    from src.routers.auth_router import verify_token

    # Crear token real
    payload = {"sub": "user@correo.com"}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    username = await verify_token(token)
    assert username == "user@correo.com"