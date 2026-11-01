import sys, os, time, statistics

MONGO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(MONGO_DIR)

import pandas as pd
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

RESULTS_DIR = os.path.join(MONGO_DIR, "results")
RUNS = 5

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
patrons = db.patrons

QUERIES = [
    {
        "name": "A: Count patrons registered in 2003",
        "type": "count",
        "filter": {"year_registered": 2003},
        "index": "year_registered",
    },
    {
        "name": "B: Patrons with over 1000 checkouts",
        "type": "find",
        "filter": {"total_checkouts": {"$gt": 1000}},
        "projection": {"total_checkouts": 1},  # _id (the patron ID) is included by default
        "index": "total_checkouts",
    },
    {
        "name": "C: Count patrons at the Chinatown branch",
        "type": "count",
        "filter": {"home_library.branch": "Chinatown"},
        "index": "home_library.branch",
    },
]


def run_query(q):
    """Run the query once and return how many results it found."""
    if q["type"] == "count":
        return db.command("count", "patrons", query=q["filter"])["n"]
    return len(list(patrons.find(q["filter"], q["projection"])))


def time_query(q):
    """Run the query RUNS times and return the median time in seconds."""
    times = []
    for _ in range(RUNS):
        start = time.perf_counter()
        run_query(q)
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def plan_stages(plan):
    """Turn MongoDB's nested query plan into a readable chain like 'FETCH -> IXSCAN'."""
    stages = []
    while plan:
        stages.append(plan.get("stage"))
        if "inputStage" in plan:
            plan = plan["inputStage"]
        elif "inputStages" in plan:
            plan = plan["inputStages"][0]
        else:
            plan = None
    return " -> ".join(s for s in stages if s)


def explain_query(q):
    """Ask MongoDB how it ran the query, with exact execution statistics."""
    if q["type"] == "count":
        command = {"count": "patrons", "query": q["filter"]}
    else:
        command = {"find": "patrons", "filter": q["filter"], "projection": q["projection"]}
    result = db.command({"explain": command, "verbosity": "executionStats"})

    winning = result["queryPlanner"]["winningPlan"]
    winning = winning.get("queryPlan", winning)  
    stats = result["executionStats"]
    return {
        "plan": plan_stages(winning),
        "docs_examined": stats["totalDocsExamined"],
        "keys_examined": stats["totalKeysExamined"],
    }

patrons.drop_indexes()

rows = []
for q in QUERIES:
    print(f"\n=== {q['name']} ===")
    results = run_query(q)
    print(f"Results: {results:,}")

    before = explain_query(q)
    before_time = time_query(q)
    print(f"Before index: {before['plan']}, docs examined {before['docs_examined']:,}, "
          f"median {before_time:.4f} sec")

    start = time.perf_counter()
    index_name = patrons.create_index(q["index"])
    build_time = time.perf_counter() - start
    print(f"Created index {index_name} in {build_time:.2f} sec")

    after = explain_query(q)
    after_time = time_query(q)
    print(f"After index:  {after['plan']}, docs examined {after['docs_examined']:,}, "
          f"keys examined {after['keys_examined']:,}, median {after_time:.4f} sec")
    print(f"Speedup: about {before_time / after_time:.0f}x")

    rows.append({
        "query": q["name"],
        "results": results,
        "plan_before": before["plan"],
        "docs_examined_before": before["docs_examined"],
        "median_sec_before": round(before_time, 4),
        "index": index_name,
        "index_build_sec": round(build_time, 2),
        "plan_after": after["plan"],
        "docs_examined_after": after["docs_examined"],
        "keys_examined_after": after["keys_examined"],
        "median_sec_after": round(after_time, 4),
        "speedup": round(before_time / after_time, 1),
    })

pd.DataFrame(rows).to_csv(os.path.join(RESULTS_DIR, "index_experiment.csv"), index=False)
print("\nSaved results to mongo/results/index_experiment.csv")
print("Indexes now on patrons:", list(patrons.index_information().keys()))

client.close()