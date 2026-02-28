from models import Base
from sqlalchemy import Column, Integer, String


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cik = Column(String, unique=True, nullable=False)
    # Add other metadata columns as needed
