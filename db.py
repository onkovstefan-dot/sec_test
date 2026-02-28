from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
import os


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Configure SQLite for better concurrent read/write behavior."""
    try:
        cursor = dbapi_connection.cursor()
        # Wait for locks instead of failing immediately.
        cursor.execute("PRAGMA busy_timeout=5000")
        # Better concurrency (readers not blocked by writers).
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
    except Exception:
        pass


DB_PATH = os.path.join(os.path.dirname(__file__), "data", "sec.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)

try:
    from sqlalchemy import event

    event.listen(engine, "connect", _set_sqlite_pragmas)
except Exception:
    pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
