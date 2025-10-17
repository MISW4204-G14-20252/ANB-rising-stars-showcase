from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from src.db.database import Base
from sqlalchemy.orm import relationship


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    city = Column(String, nullable=False)
    country = Column(String, nullable=False)

    videos = relationship("Video", back_populates="owner")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, default="uploaded")
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    owner_id = Column(Integer, ForeignKey("usuarios.id"))

    owner = relationship("Usuario", back_populates="videos")

    def to_dict(self):
        """Serializa el objeto a diccionario"""
        return {
            "id": self.id,
            "title": self.title,
            "filename": self.filename,
            "status": self.status,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processed_at": self.processed_at.isoformat()
            if self.processed_at
            else None,
            "owner_id": self.owner_id,
        }
