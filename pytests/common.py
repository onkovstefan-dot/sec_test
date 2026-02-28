"""Shared helpers for tests.

Intended usage:
- spin up a temporary SQLite database
- create all SQLAlchemy tables
- provide convenience helpers for inserting JSON/dict-like structures

These utilities keep tests small and consistent.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base

__all__ = [
    "make_sqlite_engine",
    "create_empty_sqlite_db",
    "add_dicts",
    "add_json_like",
]


def make_sqlite_engine(db_path: Path | str) -> Engine:
    """Create a SQLite engine suitable for tests."""

    if isinstance(db_path, Path):
        db_path = str(db_path)
    return create_engine(f"sqlite:///{db_path}")


def create_empty_sqlite_db(db_path: Path) -> tuple[Session, Engine]:
    """Create an empty SQLite DB file and initialize all models.

    Returns (session, engine).
    """

    engine = make_sqlite_engine(db_path)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal(), engine


def add_dicts(session: Session, model, rows: Iterable[dict[str, Any]]) -> None:
    """Bulk insert a list of dicts into a SQLAlchemy model table."""

    objs = [model(**row) for row in rows]
    session.add_all(objs)
    session.commit()


def add_json_like(session: Session, model, items: Iterable[Any]) -> None:
    """Insert JSON-like items into a model.

    - dict -> model(**dict)
    - already-constructed ORM object -> added as-is

    This allows tests to mix raw dict data and ORM objects.
    """

    objs = []
    for item in items:
        if isinstance(item, dict):
            objs.append(model(**item))
        else:
            objs.append(item)
    session.add_all(objs)
    session.commit()
