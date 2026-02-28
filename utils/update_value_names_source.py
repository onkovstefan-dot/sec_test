import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from models.value_names import ValueName  # noqa: E402

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)
session = Session()

session.query(ValueName).update({ValueName.source: 1})
session.commit()
session.close()
