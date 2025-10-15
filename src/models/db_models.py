from sqlalchemy import Column, Integer, String
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