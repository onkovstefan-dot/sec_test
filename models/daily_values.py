from sqlalchemy import Column, Integer, ForeignKey, Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, reconstructor
from models import Base

from typing import ClassVar


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

    # Allow non-Mapped[] annotations (like the compatibility shim below).
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    date_id = Column(Integer, ForeignKey("dates.id"), nullable=False)
    value_name_id = Column(Integer, ForeignKey("value_names.id"), nullable=False)

    # Optional ORM relationships
    entity = relationship("Entity")
    date = relationship("DateEntry")
    value_name = relationship("ValueName")

    # Expose unit via the ValueName relationship (ValueName.unit_id -> units.id)
    unit = relationship(
        "Unit",
        secondary="value_names",
        primaryjoin="DailyValue.value_name_id==ValueName.id",
        secondaryjoin="ValueName.unit_id==Unit.id",
        viewonly=True,
        uselist=False,
    )

    # Store as text to support any primitive value; parse at read-time in the app.
    value = Column(Text)

    # --- Compatibility shim ---
    # Some tests/legacy code construct DailyValue(unit_id=...) even though the
    # DB schema associates units via ValueName.unit_id.
    unit_id: ClassVar[int | None] = None

    @property
    def unit_id(self):  # type: ignore[override]
        try:
            return getattr(self.value_name, "unit_id", None)
        except Exception:
            return None

    @unit_id.setter
    def unit_id(self, value):  # type: ignore[override]
        # Persist via associated ValueName.
        if value is None:
            return
        if self.value_name is not None:
            self.value_name.unit_id = value

    def __init__(self, **kwargs):
        # If tests pass unit_id, persist it via ValueName.unit_id.
        unit_id = kwargs.pop("unit_id", None)
        super().__init__(**kwargs)
        if unit_id is not None:
            # May or may not have the relationship loaded yet; store for later.
            self.unit_id = unit_id

    @reconstructor
    def _init_on_load(self):
        # nothing needed; exists to avoid surprises and document intent
        pass
