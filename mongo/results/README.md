# Assignment 2 Results: MongoDB

All MongoDB results were produced by the scripts in `mongo/scripts/`. Raw
output is saved in this folder (`load_output.txt`, `queries_output.txt`,
`indexes_output.txt`), along with the query results as CSV files and the
index experiment as `index_experiment.csv`.

## Setup

- Machine: MacBook Air 2018, MacOS 14
- Database: MongoDB Community Server 8.0.34, browsed with MongoDB Compass 1.53.2
- Python driver: pymongo
- Data: SFPL_DataSF_library-usage_Jan 2023.xlsx (437,115 patrons), the same
  file used for the MySQL version
- All timings are measured from Python with `time.perf_counter()`, and each
  query was run 5 times with the median reported.

## Verifying the migration

All eight analysis queries (Q1-Q8) return exactly the same results in MongoDB
as in MySQL, including:

- Main branch: 143,471 patrons, 82.0 average checkouts
- 42,903 patrons registered in 2003
- 40,592 never-active patrons, 19 of whom have checkouts anyway
- Top borrower: patron 364974 (Adult, Visitacion Valley, 45,380 checkouts)

The missing-data counts also match: 927 patrons with no age range, 2 with no
library code, and 40,592 with no activity date. Because documents use the
same numeric IDs as MySQL (`_id` = MySQL's `patron_id`), any patron can be
compared directly between the two databases.

Findings about the library itself are unchanged from Assignment 1; see
[results/README.md](../../results/README.md).

## Loading performance

| Task | MySQL | MongoDB |
|------|-------|---------|
| Inserting 437,115 patrons | 40.1 sec | 6.0 sec |
| Whole loading script | 91.6 sec | 74.9 sec |

Most of the total time in both versions is spent reading the Excel file with
pandas (about 69 seconds), so the database itself is a small part of
loading. MongoDB's insert step: it inserts one collection of
self-contained documents with `insert_many` in batches of 5,000. The MySQL
version had to fill five lookup tables first, read back their generated IDs,
and then insert patrons with foreign keys that MySQL checks on every row.

## Query timings (Q1-Q8)

| Query | Median time |
|-------|-------------|
| Q1: Patrons and average checkouts per branch | 0.297 sec |
| Q2: Borrowing by age range | 0.385 sec |
| Q3: Average checkouts by patron type | 0.288 sec |
| Q4: Registrations per year | 0.173 sec |
| Q5: Contact preferences | 0.243 sec |
| Q6: Residents vs. non-residents | 0.244 sec |
| Q7: Never-active patrons with checkouts anyway | 0.256 sec |
| Q8: Top 10 borrowers | 0.211 sec |

None of these queries needed a join. In MySQL, Q1 joined three tables and Q8
joined four; in MongoDB, the branch and patron type names are embedded in
each patron document and reached with dot notation (for example,
`$home_library.branch`). Q1-Q7 group every patron in the collection, so they
read all 437,115 documents regardless of indexes.

## Index experiment

I timed three queries with no indexes (except the automatic one on `_id`),
created one index per query, and timed them again. `explain()` was run with
`executionStats`, which reports exact counts of documents and index keys
examined rather than estimates.

| Query | Before: plan, docs examined, time | Index | After: plan, docs examined, time | Speedup |
|-------|-----------------------------------|-------|-----------------------------------|---------|
| A: Count patrons registered in 2003 (42,903) | COLLSCAN, 437,115, 0.586 sec | `year_registered` | COUNT_SCAN, 0, 0.0185 sec | ~32x |
| B: Patrons with over 1000 checkouts (17,970) | COLLSCAN, 437,115, 0.296 sec | `total_checkouts` | FETCH + IXSCAN, 17,970, 0.080 sec | ~4x |
| C: Count patrons at Chinatown (12,759) | COLLSCAN, 437,115, 0.271 sec | `home_library.branch` | COUNT_SCAN, 0, 0.0071 sec | ~38x |

Building the indexes took 1.6, 1.1, and 1.3 seconds, similar to MySQL
(1.3 and 1.6 seconds).

### What the experiment showed

**Without an index, every query was a full collection scan.** MongoDB
examined all 437,115 documents (`COLLSCAN`), the equivalent of MySQL's type
`ALL`.

**Queries A and C were answered from the index alone.** `COUNT_SCAN` with 0
documents examined means MongoDB counted matching entries in the index
without opening any patron documents, like MySQL's "Using index." Each
examined one more key than the number of matches (42,904 and 12,760) because
the scan stops when it reaches the first key that no longer matches.

**Query B shows a real difference between the two databases.** In MySQL,
this query was a covering index, because MySQL stores the primary key inside
every secondary index. MongoDB doesn't store `_id` in other indexes, so
after finding the 17,970 matches in the index (`IXSCAN`), it had to open each
matching document (`FETCH`) to get the patron ID. It still examined only
17,970 documents instead of 437,115, but the speedup was about 4x, compared
with 14x in MySQL. Part of this query's time is also spent transferring and
converting 17,970 documents in Python. The query could be made covered by
not returning `_id` (projection `{"_id": 0, "total_checkouts": 1}`) or with a
compound index on `(total_checkouts, _id)`.

**Query C indexes a field inside an embedded document.** MongoDB indexes
`home_library.branch` just like a top-level field. In MySQL, counting patrons
by branch name needed a join through `library_codes` to `branches`; here it
is a single index lookup, and it had the largest speedup.

**A caveat about Query A.** Its "before" time (0.586 sec) is about twice the
other full scans (0.27-0.30 sec). Query A ran first, right after the indexes
were dropped, so the data was likely not yet cached in memory. Compared with
the other full-scan times, its real speedup is probably closer to 15x.

### Comparisons with MySQL

| Query | MySQL before -> after | MongoDB before -> after |
|-------|----------------------|------------------------|
| A: Count 2003 registrations | 0.217 -> 0.018 sec (~12x) | 0.586 -> 0.0185 sec (~32x) |
| B: Over 1000 checkouts | 0.215 -> 0.015 sec (~14x) | 0.296 -> 0.080 sec (~4x) |

With indexes, both databases answered Query A in about 0.018 seconds. MySQL
was faster on Query B because its index covered the query. The timing methods
also differ: MySQL times came from Workbench's duration and fetch columns,
while MongoDB times include the Python driver, so small differences should
not be over-interpreted.
