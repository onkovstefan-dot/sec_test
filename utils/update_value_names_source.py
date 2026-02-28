import os
import sys

# Allow running as standalone script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.value_names import ValueName

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)
session = Session()

session.query(ValueName).update({ValueName.source: 1})
session.commit()
session.close()
