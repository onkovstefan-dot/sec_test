from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint
from models import Base


class DailyValueText(Base):
    __tablename__ = "daily_values_text"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "date_id",
            "value_name_id",
            name="uq_daily_values_text_entity_date_value",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    date_id = Column(Integer, ForeignKey("dates.id"), nullable=False)
    value_name_id = Column(Integer, ForeignKey("value_names.id"), nullable=False)

    # Store non-numeric values (including identifiers, forms, booleans, etc.)
    value_text = Column(String)
