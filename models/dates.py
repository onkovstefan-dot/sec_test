from models import Base
from sqlalchemy import Column, Integer, Date


class DateEntry(Base):
    __tablename__ = "dates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False)
