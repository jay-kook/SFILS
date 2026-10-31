import sys, os, time

# mongo/ folder (for config.py) and the repo root (for the data folder)
MONGO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(MONGO_DIR)
sys.path.append(MONGO_DIR)

import pandas as pd
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

DATA_FILE = os.path.join(REPO_ROOT, "data", "library_usage.xlsx")
BATCH_SIZE = 5000


def clean(value):
    """Turn missing values (NaN) and blank text into None, stored as null in MongoDB."""
    if pd.isna(value):
        return None
    if isinstance(value, str) and value == "":
        return None
    return value


start_total = time.perf_counter()

# 1. Read and clean the data
print("Reading Excel file...")
df = pd.read_excel(DATA_FILE)
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

# sorts order for age ranges
age_labels = sorted(set(df["Age Range"].dropna()), key=lambda label: int(label.split()[0]))
age_sort_order = {label: i + 1 for i, label in enumerate(age_labels)}

# 2. Build one document per patron
print("Building documents...")
documents = []
rows = zip(
    df["Patron Type Code"].tolist(),
    df["Patron Type Definition"].tolist(),
    df["Age Range"].tolist(),
    df["Home Library Code"].tolist(),
    df["Home Library Definition"].tolist(),
    df["Notification Preference Code"].tolist(),
    df["Notification Code Definition"].tolist(),
    df["Total Checkouts"].tolist(),
    df["Total Renewals"].tolist(),
    df["Circulation Active Month"].tolist(),
    df["Circulation Active Year"].tolist(),
    df["Provided Email Address"].tolist(),
    df["Within San Francisco County"].tolist(),
    df["Year Patron Registered"].tolist(),
)

for patron_id, (type_code, type_name, age, lib_code, lib_name, notif_code, notif_name,
                checkouts, renewals, month, year, email, in_sf, registered) in enumerate(rows, start=1):
    documents.append({
        "_id": patron_id,
        "patron_type": {"code": int(type_code), "name": type_name},
        "age_range": None if pd.isna(age) else {"label": age, "sort_order": age_sort_order[age]},
        "home_library": None if pd.isna(lib_code) else {"code": lib_code, "branch": lib_name},
        "notification": {"code": notif_code, "name": "None" if pd.isna(notif_name) else notif_name},
        "total_checkouts": int(checkouts),
        "total_renewals": int(renewals),
        "circulation_active": None if pd.isna(year) else {"month": clean(month), "year": int(year)},
        "provided_email": bool(email),
        "within_sf_county": bool(in_sf),
        "year_registered": int(registered),
    })

# 3. Insert into MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

db.patrons.drop()

print("Inserting documents...")
start_insert = time.perf_counter()
for i in range(0, len(documents), BATCH_SIZE):
    db.patrons.insert_many(documents[i:i + BATCH_SIZE])
insert_seconds = time.perf_counter() - start_insert

count = db.patrons.count_documents({})
print(f"patrons: {count} documents")
client.close()

total_seconds = time.perf_counter() - start_total
print(f"\nInserting documents took {insert_seconds:.1f} seconds")
print(f"Whole script took {total_seconds:.1f} seconds")