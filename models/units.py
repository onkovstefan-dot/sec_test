from models import Base
from sqlalchemy import Column, Integer, String


class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
