from models import Base
from sqlalchemy import Column, Integer, String


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cik = Column(String, unique=True, nullable=False)

    # Optional metadata
    company_name = Column(String, nullable=True)
    country = Column(String, nullable=True)
    sector = Column(String, nullable=True)
