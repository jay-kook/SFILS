# Results and Findings

## Setup

- Machine: MacBook Air, 2018
- Database: MySQL 8.4.11, accessed through MySQL Workbench
- Data: SFPL_DataSF_library-usage_Jan 2023.xlsx (437,115 patrons, 14 columns)

## Loading performance

| Task | Time |
|------|------|
| Whole load_data.py script | 91.6 sec |
| Inserting 437,115 patron rows | 40.1 sec |

Most of the script's time goes to reading the Excel file with pandas. The
patrons are inserted in batches of 5,000 rows using executemany, which is
much faster than inserting one row at a time.

## Index experiment

I timed two queries on columns with no index, added an index to each column,
and timed them again. Each query was run 5 times and the median is reported.
For Query B, which returns 17,970 rows, I used total time (duration + fetch).

| Query | Without index | With index | Speedup |
|-------|---------------|------------|---------|
| A: `COUNT(*) WHERE year_registered = 2003` | 0.217 sec | 0.018 sec | ~12x |
| B: `WHERE total_checkouts > 1000` (17,970 rows) | 0.215 sec | 0.015 sec | ~14x |

What EXPLAIN showed:

| Query | Before | After |
|-------|--------|-------|
| A | type ALL, no key, ~435,360 rows examined | type ref, idx_patrons_year_registered, ~84,922 rows, "Using index" |
| B | type ALL, no key, ~435,360 rows examined | type range, idx_patrons_total_checkouts, ~33,470 rows, "Using where; Using index" |

Building the indexes took 1.3 sec (year_registered) and 1.6 sec (total_checkouts).

Without an index, MySQL had to do a full table scan for both queries, checking
every one of the roughly 437,000 patron rows to find the matches. After adding
the indexes, MySQL used them to jump straight to the matching values, and both
queries became 12 to 14 times faster. Both indexes also turned out to be
covering indexes ("Using index"), meaning MySQL could answer the query from the
index alone without reading the table at all. Query B is covered because MySQL
automatically stores the primary key (patron_id) inside every index. Query B's
fetch time also dropped sharply (from about 0.19 to 0.013 sec), because MySQL
no longer had to crawl through the whole table while sending results back, and
its results came back sorted by total_checkouts because they were read in index
order. Indexes are not free, though: each one took over a second to build, uses
extra storage, and makes inserts and updates slightly slower, so they are worth
adding only on columns that queries actually filter or sort by. MySQL had
already indexed the four foreign key columns in patrons automatically, which is
why the experiment used year_registered and total_checkouts.

Note: EXPLAIN's row counts are estimates. Before the index, MySQL guessed that
33% of rows would match Query B, but only 4.1% did, because it had no
statistics on that column.

## Findings about the San Francisco Public Library

Full query results are in the CSV files in this folder, and the queries are in
scripts/queries.sql. All percentages are out of 437,115 patrons.

An important caveat for all checkout numbers: total_checkouts is a lifetime
total since the patron registered, not a yearly rate. Patrons who registered
in 2003 have had about 20 years to accumulate checkouts, while those who
registered in 2022 have had about one. Groups with older accounts will
naturally show higher totals.

### Branches (q1_branches.csv)
Main is by far the largest branch, with 143,471 patrons, about 33% of everyone
in the system. The next largest, Richmond, has 20,736. Surprisingly, Main's
patrons borrow among the least: they average 82 checkouts, compared with 348
at Chinatown, 320 at Ortega, and 272 at Portola. Only Mission Bay (77) is lower.
One possible explanation is that Main, as the central downtown library, signs
up many casual or one-time users, while neighborhood branches have more
regular local borrowers. ("Unknown" shows the highest average, 409, but it has
only 127 patrons, so that number isn't meaningful.)

### Age (q2_age.csv)
The largest age group is 25 to 34 (92,790 patrons, 21%), but it has the lowest
average checkouts of any group, at 48. Borrowing rises steadily with age after
that, reaching 362 for ages 65 to 74 and 422 for patrons 75 and over, almost
nine times the 25 to 34 group. Teens (10 to 19) are also strong borrowers at
207, higher than people in their twenties and thirties. Renewals follow a
similar pattern, peaking at 158 for ages 65 to 74. Part of the age effect is
likely the lifetime-total caveat above, since older patrons tend to have held
their cards longer.

### Patron types (q3_patron_types.csv)
Most patrons are Adults (271,588, 62%), followed by Juvenile (13%), Senior
(11%), and Teen (9%). The heaviest borrowers are library employees: Retired
Staff average 1,356 checkouts and Staff average 1,205, about ten times a
regular Adult (126). Seniors (393) and Teens (235) also out-borrow Adults. At
the other end, Digital Access Cards (3.6), Welcome cards (3.5), and
Bibliocommons accounts (0) have almost no checkouts, which makes sense if
these are online-only or limited accounts. Some types are very small (Business
has 8 patrons, At User Juvenile has 9), so their averages are less reliable.

### Registration years (q4_registration_years.csv)
The data covers registrations from 2003 to 2022. The busiest year was 2019,
with 56,437 registrations. 2003 stands out with 42,903 registrations, about
nine times more than 2004 (4,738) or 2005 (5,069). Since 2003 is also the
earliest year in the data, one possible explanation is that it groups everyone
who registered in 2003 or earlier, or that older records were moved into a new
system that year. The data alone can't confirm which. Registrations also
dropped from 56,437 in 2019 to about 33,000 in 2020 and 2021, then rebounded
to 52,377 in 2022, a pattern that may reflect library closures during the
COVID-19 pandemic.

### Contact preferences (q5_notifications.csv)
Email is overwhelmingly preferred: 391,614 patrons (89.6%). Phone is a distant
second (35,559, 8.1%), followed by Print (7,242, 1.7%). 2,700 patrons (0.6%)
have no preference recorded.

### Residents vs. non-residents (q6_residents.csv)
84.5% of patrons (369,259) live within San Francisco County, and 15.5%
(67,856) live outside it. Residents borrow far more, averaging 179 checkouts
compared with 62 for non-residents, almost three times as much.

### Heaviest borrowers (q8_top_borrowers.csv)
The top borrower, an Adult at Visitacion Valley, has 45,380 lifetime
checkouts. The top 10 range from 18,906 to 45,380, and all are Adults or
Seniors. Main appears four times and Chinatown three times, matching
Chinatown's high average from q1. Seven of the ten registered in 2003, which
fits the lifetime-total caveat (these are the oldest accounts) and may also
relate to the 2003 registration spike. Even over 20 years, 45,380 checkouts is
about six items a day, so these extreme values could reflect institutional or
shared use of a card rather than one individual.

### Data quality (q7_data_quality.csv)
- 40,592 patrons (9.3%) have no circulation active month or year. Almost all of
  them have zero checkouts, which fits patrons who never used their card, but
  19 of them have checkouts anyway, which is an inconsistency in the source
  data.
- 927 patrons (0.2%) have no age range, and 2 patrons have no home library
  code. Both are stored as NULL rather than filled in with a guess.
- 2,700 patrons have the notification code "-", which has no definition in the
  data. I stored it with the name "None."
- The library uses 67 codes for only 30 branches. For example, Bookmobile has
  9 codes and Main has 4. I stored this as a library_codes table that points to
  a branches table, so each branch name is stored only once.
- The original spreadsheet's column headers contained line breaks, and the
  blank circulation months were stored as empty text rather than missing
  values. Both had to be cleaned in load_data.py before loading.