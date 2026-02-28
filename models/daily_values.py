from sqlalchemy import Column, Integer, Float, ForeignKey
from models import Base

class DailyValue(Base):
    __tablename__ = 'daily_values'
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey('entities.id'), nullable=False)
    date_id = Column(Integer, ForeignKey('dates.id'), nullable=False)
    value_name_id = Column(Integer, ForeignKey('value_names.id'), nullable=False)
    value = Column(Float)
