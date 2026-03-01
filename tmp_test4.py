import pytest

from models.daily_values import DailyValue
from models.units import Unit
from models.value_names import ValueName
from pytests.common import create_empty_sqlite_db

import utils.populate_daily_values as m

session, engine = create_empty_sqlite_db("test_sec4.db")

m.engine = engine
m.session = session

unit_id = m.get_or_create_unit("NA", session=session).id
entity = m.get_or_create_entity("0000001750", company_name="AAR CORP.", session=session)

unit_cache = {}
value_name_cache = {}
date_cache = {}

def get_unit_id_cached(name):
    key = (name or "NA").strip() or "NA"
    if key in unit_cache:
        return unit_cache[key]
    unit_cache[key] = m.get_or_create_unit(key, session=session).id
    return unit_cache[key]

def get_value_name_id_cached(name, unit_id):
    key = (name, unit_id)
    if key in value_name_cache:
        return value_name_cache[key]
    value_name_cache[key] = m.get_or_create_value_name(name, unit_id=unit_id, session=session).id
    return value_name_cache[key]

def get_date_id_cached(date_str):
    if date_str in date_cache:
        return date_cache[date_str]
    de = m.get_or_create_date_entry(date_str, session=session)
    date_cache[date_str] = de.id
    return de.id

sample_companyfacts_dict = {'cik': 1750, 'entityName': 'AAR CORP.', 'facts': {'us-gaap': {'Assets': {'label': 'Assets', 'units': {'USD': [{'end': '2010-05-31', 'val': 1481100000}]}}}}}

planned, dups = m.process_companyfacts_file(
    data=sample_companyfacts_dict,
    source="companyfacts",
    filename="companyfacts_sample.json",
    entity_id=entity.id,
    get_unit_id_cached=get_unit_id_cached,
    get_value_name_id_cached=get_value_name_id_cached,
    get_date_id_cached=get_date_id_cached,
    session=session
)

print(f"Planned: {planned}, Dups: {dups}")
def _default_session(provided):
    return provided if provided is not None else m.session

print(repr(m.session))

