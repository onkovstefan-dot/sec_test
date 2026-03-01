from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy import Column, Integer
from sqlalchemy.dialects.sqlite import insert

Base = declarative_base()

class M(Base):
    __tablename__ = "m"
    id = Column(Integer, primary_key=True)
    val = Column(Integer, unique=True)

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
session = Session(engine)

def do_insert(session, val):
    stmt = insert(M).values([{"val": val}]).prefix_with("OR IGNORE")
    res = session.execute(stmt)
    session.flush()
    print("rowcount", res.rowcount)

do_insert(session, 1)
print(session.query(M).count())
