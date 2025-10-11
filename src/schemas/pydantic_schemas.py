# from typing import Optional
from pydantic import BaseModel

# Esquema base que permite establecer atributos comunes
# al escribir o leer datos
class UsuarioBase(BaseModel):
    nombre: str

# Incluye datos necesarios para la creacion de un usuario
class UsuarioCreateSchema (UsuarioBase):
    contrasena: str

class UsuarioLoginSchema (UsuarioBase):
    contrasena: str

# Usado cuando se retorne una instancia desde el API
class UsuarioSchema(UsuarioBase):
    id: int
    class Config:
        orm_mode = True


class TokenData(BaseModel):
    access_token: str 
    token_type: str
