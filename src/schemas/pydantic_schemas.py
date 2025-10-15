from pydantic import BaseModel
from datetime import datetime

# Esquema base común para lecturas o escrituras
class UsuarioBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    city: str
    country: str


# Esquema para creación de usuario (registro)
class UsuarioCreateSchema(UsuarioBase):
    password1: str
    password2: str


# Esquema para inicio de sesión
class UsuarioLoginSchema(BaseModel):
    email: str
    password: str


# Esquema usado al retornar un usuario desde el API
class UsuarioSchema(UsuarioBase):
    id: int

    class Config:
        orm_mode = True


# Esquema para token JWT
class TokenData(BaseModel):
    access_token: str
    token_type: str



class VideoBase(BaseModel):
    title: str

class VideoCreate(VideoBase):
    pass

class VideoOut(VideoBase):
    id: int
    filename: str
    status: str
    uploaded_at: datetime
    processed_at: datetime | None

    class Config:
        orm_mode = True