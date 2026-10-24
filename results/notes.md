# NOTES

## Query findings (Q1–Q8)

Q1: Main has the most patrons (143,471) but low avg checkouts (82). Chinatown highest real branch avg (348).
Q2: 25–34 is the biggest group but lowest avg checkouts (48). Borrowing rises with age; 75+ highest (422).
Q3: Retired Staff (1,356) and Staff (1,205) borrow ~10x a regular Adult (126). Digital/Welcome cards near 0.
Q4: 2003 spike (42,903), ~9x 2004. Busiest year 2019 (56,437). Dip in 2020–2021, rebound 2022.
Q5: Email 89.6%, Phone 8.1%, Print 1.7%, None 0.6%.
Q6: SF residents avg 179 checkouts vs 62 for non-residents (~3x).
Q7: 40,592 never-active patrons; 19 of them have checkouts anyway (data inconsistency).
Q8: Top borrower 45,380 checkouts. Top 10 all Adult/Senior; 7 of 10 registered in 2003.

## Index experiment

### Query A: SELECT COUNT(*) FROM patrons WHERE year_registered = 2003;
Result: 42,903 patrons

Before index:
- EXPLAIN: type ALL, key NULL, rows 435,360 (full table scan)
- Times: 0.209, 0.217, 0.217, 0.216, 0.238 sec
- Median: 0.217 sec

After index:
- EXPLAIN: type ref, key idx_patrons_year_registered, rows 84,922 (estimate; actual 42,903), Extra "Using index"
- Times: 0.018, 0.017, 0.020, 0.014, 0.019 sec
- Median: 0.018 sec (about 12x faster)

### Query B: SELECT patron_id, total_checkouts FROM patrons WHERE total_checkouts > 1000;
Result: 17,970 patrons

Before index:
- EXPLAIN: type ALL, key NULL, rows 435,360 (full table scan), filtered 33.33
- Times (duration + fetch = total):
  0.034 + 0.248 = 0.282
  0.048 + 0.207 = 0.255
  0.026 + 0.189 = 0.215
  0.017 + 0.193 = 0.210
  0.021 + 0.188 = 0.209
- Median total: 0.215 sec

After index:
- EXPLAIN: type range, key idx_patrons_total_checkouts, rows 33,470 (estimate; actual 17,970), Extra "Using where; Using index"
- Times (duration + fetch = total):
  0.0012 + 0.0097 = 0.0109
  0.0013 + 0.013 = 0.0143
  0.0020 + 0.016 = 0.0180
  0.0018 + 0.013 = 0.0148
  0.0013 + 0.015 = 0.0163
- Median total: 0.015 sec (about 14x faster)

### Index build times
- idx_patrons_year_registered: 1.311 sec
- idx_patrons_total_checkouts: 1.567 sec

### Observations
- Without indexes, both queries did a full table scan (type ALL), checking about 435,000 rows.
- With indexes, MySQL used them directly (type ref for Query A, range for Query B), and both queries got 12-14x faster.
- Both became covering indexes ("Using index"): MySQL answered the queries from the index alone without reading the table. Query B is covered because MySQL stores the primary key (patron_id) inside every index.
- Query B returns 17,970 rows, so most of its time is fetch time (moving rows to Workbench), not duration. I compared total time (duration + fetch).
- Query B's fetch time also dropped (about 0.19 → 0.013 sec), because MySQL no longer had to scan the whole table to find matching rows.
- After indexing, Query B's results came back sorted by total_checkouts (starting at 1001), because MySQL read them in index order.
- EXPLAIN's row counts are estimates. Before the index it guessed 33.33% of rows would match Query B, but only 4.1% did.
- Indexes have a cost: building them took about 1.3-1.6 seconds each, and they use extra storage and slow down inserts slightly. The foreign key columns were already indexed automatically by MySQL.