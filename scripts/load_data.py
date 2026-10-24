import sys, os, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import mysql.connector
from config import DB_CONFIG

BATCH_SIZE = 5000


def none_if_missing(value):
    """Turn missing values (NaN) and blank text into None, which MySQL stores as NULL."""
    if pd.isna(value):
        return None
    if isinstance(value, str) and value == "":
        return None
    return value


start_total = time.perf_counter()

# ---------- 1. Read and clean the data ----------
print("Reading Excel file...")
df = pd.read_excel("data/library_usage.xlsx")
df.columns = [c.split("\n")[0].strip() for c in df.columns]

text_columns = [
    "Patron Type Definition",
    "Age Range",
    "Home Library Code",
    "Home Library Definition",
    "Circulation Active Month",
    "Notification Preference Code",
    "Notification Code Definition",
]
for col in text_columns:
    df[col] = df[col].str.strip()

print(f"Loaded {len(df)} rows")

# ---------- 2. Connect and empty the tables ----------
conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
for table in ["patrons", "library_codes", "branches",
              "notification_preferences", "age_ranges", "patron_types"]:
    cursor.execute(f"TRUNCATE TABLE {table}")
cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

# ---------- 3. Fill the lookup tables ----------

# patron_types: each code already has a name in the data
pairs = df[["Patron Type Code", "Patron Type Definition"]].drop_duplicates()
patron_type_rows = [
    (int(code), name)
    for code, name in zip(pairs["Patron Type Code"].tolist(),
                          pairs["Patron Type Definition"].tolist())
]
cursor.executemany(
    "INSERT INTO patron_types (patron_type_code, patron_type_name) VALUES (%s, %s)",
    patron_type_rows,
)
print(f"patron_types: {len(patron_type_rows)} rows")

# age_ranges: sort by the first number in the label ("0 to 9 years" -> 0)
labels = sorted(set(df["Age Range"].dropna()), key=lambda label: int(label.split()[0]))
age_rows = [(label, i + 1) for i, label in enumerate(labels)]
cursor.executemany(
    "INSERT INTO age_ranges (age_range_label, sort_order) VALUES (%s, %s)",
    age_rows,
)
cursor.execute("SELECT age_range_label, age_range_id FROM age_ranges")
age_ids = dict(cursor.fetchall())
print(f"age_ranges: {len(age_rows)} rows")

# notification_preferences: the '-' code has no name, so call it 'None'
pairs = df[["Notification Preference Code", "Notification Code Definition"]].drop_duplicates()
notification_rows = [
    (code, "None" if pd.isna(name) else name)
    for code, name in zip(pairs["Notification Preference Code"].tolist(),
                          pairs["Notification Code Definition"].tolist())
]
cursor.executemany(
    "INSERT INTO notification_preferences (notification_code, notification_name) VALUES (%s, %s)",
    notification_rows,
)
print(f"notification_preferences: {len(notification_rows)} rows")

# branches: each branch name once
branch_names = sorted(set(df["Home Library Definition"].dropna()))
cursor.executemany(
    "INSERT INTO branches (branch_name) VALUES (%s)",
    [(name,) for name in branch_names],
)
cursor.execute("SELECT branch_name, branch_id FROM branches")
branch_ids = dict(cursor.fetchall())
print(f"branches: {len(branch_names)} rows")

# library_codes: each code points to its branch
pairs = df[["Home Library Code", "Home Library Definition"]].dropna().drop_duplicates()
library_code_rows = [
    (code, branch_ids[name])
    for code, name in zip(pairs["Home Library Code"].tolist(),
                          pairs["Home Library Definition"].tolist())
]
cursor.executemany(
    "INSERT INTO library_codes (library_code, branch_id) VALUES (%s, %s)",
    library_code_rows,
)
print(f"library_codes: {len(library_code_rows)} rows")

# ---------- 4. Fill the patrons table ----------
print("Preparing patron rows...")
patron_rows = []
for (ptype, age, lib_code, notif_code, checkouts, renewals,
     month, year, email, in_sf, registered) in zip(
        df["Patron Type Code"].tolist(),
        df["Age Range"].tolist(),
        df["Home Library Code"].tolist(),
        df["Notification Preference Code"].tolist(),
        df["Total Checkouts"].tolist(),
        df["Total Renewals"].tolist(),
        df["Circulation Active Month"].tolist(),
        df["Circulation Active Year"].tolist(),
        df["Provided Email Address"].tolist(),
        df["Within San Francisco County"].tolist(),
        df["Year Patron Registered"].tolist()):
    patron_rows.append((
        int(ptype),
        None if pd.isna(age) else age_ids[age],
        none_if_missing(lib_code),
        notif_code,
        int(checkouts),
        int(renewals),
        none_if_missing(month),
        None if pd.isna(year) else int(year),
        bool(email),
        bool(in_sf),
        int(registered),
    ))

insert_patron = """
    INSERT INTO patrons (
        patron_type_code, age_range_id, home_library_code, notification_code,
        total_checkouts, total_renewals, active_month, active_year,
        provided_email, within_sf_county, year_registered
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

print("Inserting patrons...")
start_patrons = time.perf_counter()
for i in range(0, len(patron_rows), BATCH_SIZE):
    cursor.executemany(insert_patron, patron_rows[i:i + BATCH_SIZE])
patron_seconds = time.perf_counter() - start_patrons
print(f"patrons: {len(patron_rows)} rows")

# ---------- 5. Save and report ----------
conn.commit()
cursor.close()
conn.close()

total_seconds = time.perf_counter() - start_total
print(f"\nInserting patrons took {patron_seconds:.1f} seconds")
print(f"Whole script took {total_seconds:.1f} seconds")