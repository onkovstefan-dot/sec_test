import importlib
m = importlib.import_module("utils.populate_daily_values")

print("Before:", id(m.session))

m.session = "mocked"
print("Module level:", id(m.session))

print("Returned:", id(m._default_session(None)))

