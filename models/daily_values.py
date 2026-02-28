from sqlalchemy import Column, Integer, ForeignKey, Text
from sqlalchemy import UniqueConstraint
from models import Base


class DailyValue(Base):
    __tablename__ = "daily_values"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "date_id",
            "value_name_id",
            name="uq_daily_values_entity_date_value",
        ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    date_id = Column(Integer, ForeignKey("dates.id"), nullable=False)
    value_name_id = Column(Integer, ForeignKey("value_names.id"), nullable=False)

    # Store as text to support any primitive value; parse at read-time in the app.
    value = Column(Text)
