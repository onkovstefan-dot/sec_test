from models import Base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import ForeignKey

from utils.time_utils import utcnow_sa_default


class ValueName(Base):
    __tablename__ = "value_names"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

    # Unit of measure (nullable; treat NULL as NA).
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)

    # Source system identifier (e.g. 'sec').
    source = Column(String, nullable=False, default="sec")

    added_on = Column(DateTime, nullable=False, default=utcnow_sa_default)
    valid_until = Column(DateTime, nullable=True)
