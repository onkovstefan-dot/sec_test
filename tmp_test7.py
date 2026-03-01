import pytest

from models.daily_values import DailyValue
from pytests.common import create_empty_sqlite_db

import utils.populate_daily_values as m

session, engine = create_empty_sqlite_db("test_sec4.db")

print("1. Module session id:", id(m.session))
m.session = session
print("2. Module session id after mock:", id(m.session))

ret = m._default_session(None)
print("3. Ret id:", id(ret))

m._init_default_db_globals()
ret = m._default_session(None)
print("4. Ret id:", id(ret))


