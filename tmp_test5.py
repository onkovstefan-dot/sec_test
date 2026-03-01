import subprocess

def run_pytest():
    proc = subprocess.run(["pytest", "-q", "pytests/test_populate_daily_values.py", "-k", "test_process_companyfacts_file_inserts_daily_value"], capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print("Failed!")

with open("utils/populate_daily_values.py", "r") as f:
    text = f.read()

# patch text 
text2 = text.replace("duplicates = max(inserts_planned - inserted, 0)", 'print("DEBUG", repr(session), inserts_planned, inserted)\n    duplicates = max(inserts_planned - inserted, 0)')

with open("utils/populate_daily_values.py", "w") as f:
    f.write(text2)

run_pytest()

with open("utils/populate_daily_values.py", "w") as f:
    f.write(text)

