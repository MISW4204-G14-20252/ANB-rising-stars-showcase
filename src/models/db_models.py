from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
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
    votes = relationship("Vote", back_populates="user")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, default="uploaded")  # uploaded | processed | public
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    owner_id = Column(Integer, ForeignKey("usuarios.id"))
    is_public = Column(Boolean, default=False)
    votes_count = Column(Integer, default=0)

    owner = relationship("Usuario", back_populates="videos")
    votes = relationship("Vote", back_populates="video")

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
            "is_public": self.is_public,
            "votes_count": self.votes_count,
        }


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


    video = relationship("Video", back_populates="votes")
    user = relationship("Usuario", back_populates="votes")
