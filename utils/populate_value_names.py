import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.value_names import Base, ValueName

SUBMISSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "raw_data", "submissions"
)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")

engine = create_engine(f"sqlite:///{DB_PATH}")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

unique_names = set()
for filename in os.listdir(SUBMISSIONS_DIR):
    if filename.endswith(".json"):
        with open(os.path.join(SUBMISSIONS_DIR, filename), "r", encoding="utf-8") as f:
            data = json.load(f)
        filings = data.get("filings", {})
        recent = filings.get("recent", {})
        unique_names.update(recent.keys())

for name in unique_names:
    if not session.query(ValueName).filter_by(name=name).first():
        session.add(ValueName(name=name))

session.commit()
session.close()
