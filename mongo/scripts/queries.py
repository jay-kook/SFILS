import sys, os, time, statistics

MONGO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(MONGO_DIR)

import pandas as pd
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

RESULTS_DIR = os.path.join(MONGO_DIR, "results")
RUNS = 5

client = MongoClient(MONGO_URI)
patrons = client[DB_NAME].patrons
total_patrons = patrons.count_documents({})

QUERIES = [
    (
        "Q1: Patrons and average checkouts per branch",
        "q1_branches.csv",
        [
            {"$match": {"home_library": {"$ne": None}}},
            {"$group": {
                "_id": "$home_library.branch",
                "patrons": {"$sum": 1},
                "avg_checkouts": {"$avg": "$total_checkouts"},
            }},
            {"$sort": {"patrons": -1}},
            {"$project": {
                "_id": 0,
                "branch_name": "$_id",
                "patrons": 1,
                "avg_checkouts": {"$round": ["$avg_checkouts", 1]},
            }},
        ],
    ),
    (
        "Q2: Borrowing by age range",
        "q2_age.csv",
        [
            {"$match": {"age_range": {"$ne": None}}},
            {"$group": {
                "_id": {"label": "$age_range.label", "order": "$age_range.sort_order"},
                "patrons": {"$sum": 1},
                "avg_checkouts": {"$avg": "$total_checkouts"},
                "avg_renewals": {"$avg": "$total_renewals"},
            }},
            {"$sort": {"_id.order": 1}},
            {"$project": {
                "_id": 0,
                "age_range_label": "$_id.label",
                "patrons": 1,
                "avg_checkouts": {"$round": ["$avg_checkouts", 1]},
                "avg_renewals": {"$round": ["$avg_renewals", 1]},
            }},
        ],
    ),
    (
        "Q3: Average checkouts by patron type",
        "q3_patron_types.csv",
        [
            {"$group": {
                "_id": "$patron_type.name",
                "patrons": {"$sum": 1},
                "avg_checkouts": {"$avg": "$total_checkouts"},
            }},
            {"$sort": {"avg_checkouts": -1}},
            {"$project": {
                "_id": 0,
                "patron_type_name": "$_id",
                "patrons": 1,
                "avg_checkouts": {"$round": ["$avg_checkouts", 1]},
            }},
        ],
    ),
    (
        "Q4: Registrations per year",
        "q4_registration_years.csv",
        [
            {"$group": {"_id": "$year_registered", "patrons": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
            {"$project": {"_id": 0, "year_registered": "$_id", "patrons": 1}},
        ],
    ),
    (
        "Q5: Contact preferences",
        "q5_notifications.csv",
        [
            {"$group": {"_id": "$notification.name", "patrons": {"$sum": 1}}},
            {"$sort": {"patrons": -1}},
            {"$project": {
                "_id": 0,
                "notification_name": "$_id",
                "patrons": 1,
                "percent": {"$round": [
                    {"$multiply": [{"$divide": ["$patrons", total_patrons]}, 100]}, 1
                ]},
            }},
        ],
    ),
    (
        "Q6: Residents vs. non-residents",
        "q6_residents.csv",
        [
            {"$group": {
                "_id": "$within_sf_county",
                "patrons": {"$sum": 1},
                "avg_checkouts": {"$avg": "$total_checkouts"},
            }},
            {"$sort": {"_id": -1}},
            {"$project": {
                "_id": 0,
                "within_sf_county": "$_id",
                "patrons": 1,
                "avg_checkouts": {"$round": ["$avg_checkouts", 1]},
            }},
        ],
    ),
    (
        "Q7: Never-active patrons with checkouts anyway",
        "q7_data_quality.csv",
        [
            {"$match": {"circulation_active": None}},
            {"$group": {
                "_id": None,
                "never_active": {"$sum": 1},
                "have_checkouts_anyway": {
                    "$sum": {"$cond": [{"$gt": ["$total_checkouts", 0]}, 1, 0]}
                },
            }},
            {"$project": {"_id": 0}},
        ],
    ),
    (
        "Q8: Top 10 borrowers",
        "q8_top_borrowers.csv",
        [
            {"$sort": {"total_checkouts": -1}},
            {"$limit": 10},
            {"$project": {
                "_id": 0,
                "patron_id": "$_id",
                "patron_type_name": "$patron_type.name",
                "branch_name": "$home_library.branch",
                "total_checkouts": 1,
                "year_registered": 1,
            }},
        ],
    ),
]

summary = []
for title, filename, pipeline in QUERIES:
    times = []
    for _ in range(RUNS):
        start = time.perf_counter()
        results = list(patrons.aggregate(pipeline))
        times.append(time.perf_counter() - start)
    median = statistics.median(times)

    df = pd.DataFrame(results)
    df.to_csv(os.path.join(RESULTS_DIR, filename), index=False)

    print(f"\n{title}   (median of {RUNS} runs: {median:.3f} sec)")
    print(df.head(10).to_string(index=False))
    summary.append((title, median))

print("\n - Timing summary (median of 5 runs) - ")
for title, median in summary:
    print(f"{median:8.3f} sec   {title}")

client.close()
