from sqlalchemy import Column, Integer, String
# from sqlalchemy.orm import relationship
from src.db.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50))
    contrasena = Column(String(50))
