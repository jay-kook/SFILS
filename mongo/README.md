# MISFILS
MISFILS: The MongoDB-based Implementation for the San Francisco Integrated Library System.

# Assignment 2: SFILS on MongoDB

This folder contains Assignment 2: the San Francisco Integrated Library
System from Assignment 1, translated from MySQL to MongoDB. It loads the same
San Francisco Public Library patron data into MongoDB, reruns the same
analysis, measures index performance with `explain()`, and provides the same
terminal app, but now with MongoDB instead.

**All Assignment 2 work is inside this `mongo` folder.** The MySQL project in
`app/`, `scripts/`, `docs/`, and `results/` was not modified and still works
as before. The only shared item is the dataset, which both versions read from
the `data/` folder at the top of the repository.

## What's in this folder?

| File / folder | What it does |
|---|---|
| `config.py` | MongoDB connection settings (`mongodb://localhost:27017`, database `sfils`) |
| `requirements.txt` | Python packages needed |
| `scripts/test_connection.py` | Checks that Python can connect to MongoDB |
| `scripts/load_data.py` | Reads the Excel file, cleans it, and loads 437,115 patron documents |
| `scripts/queries.py` | Runs Q1-Q8 as aggregation pipelines, times them, and saves results as CSV |
| `scripts/indexes.py` | Index experiment: times and explains queries before and after creating indexes |
| `app/main.py` | The terminal app, using MongoDB |
| `results/` | Timings, the index experiment, the comparison with MySQL, and query results |

## How to set up and run

These steps rebuild the project from scratch on a Mac.

### 1. Getting the code

```bash
git clone https://github.com/jay-kook/SFILS.git
cd SFILS
```

### 2. Installing MongoDB Community Server

I installed MongoDB 8.0.34 from MongoDB's website rather than Homebrew.
Homebrew no longer provided ready-built packages for macOS 14, so
`brew install mongodb-community` tried to compile its dependencies from
source, which failed.

1. Go to https://www.mongodb.com/try/download/community and choose version
   8.0.x, platform **macOS x64** (Intel) or **macOS ARM 64** (Apple Silicon),
   and package **tgz**.
2. Unpack it and move it to your home folder (adjust the name to match your
   download):

```bash
cd ~/Downloads
tar -xvf mongodb-macos-x86_64-8.0.34.tgz
mv mongodb-macos-x86_64-8.0.34 ~/mongodb
```

3. Allowing macOS to run it, and adding it to your PATH:

```bash
xattr -dr com.apple.quarantine ~/mongodb
echo 'export PATH="$HOME/mongodb/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
mongod --version
```

On a newer macOS with Homebrew support, `brew tap mongodb/brew` followed by
`brew install mongodb-community` also works.

### 3. Starting the MongoDB server

```bash
mkdir -p ~/data/db ~/data/log/mongodb
mongod --dbpath ~/data/db --logpath ~/data/log/mongodb/mongo.log --fork
```

This must be run again after every restart. This checks whether it's already
running, use `pgrep -l mongod`. To stop it, use `pkill mongod`.

Alternatively, install [MongoDB Compass](https://www.mongodb.com/try/download/compass)
to browse the data, and connect to `mongodb://localhost:27017`.

### 4. Setting up Python

```bash
conda create -n sfils python=3.11 -y
conda activate sfils
pip install -r mongo/requirements.txt
```

### 5. Downloading the dataset

The data file is not stored in the repository because of its size. If you
already set up the MySQL version, it's already in `data/`. Otherwise:

```bash
mkdir -p data
curl -L -o data/library_usage.xlsx "https://data.sfgov.org/api/views/qzz6-2jup/files/ecfd0051-fe40-43c3-a17d-caeff0f1503f?download=true&filename=SFPL_DataSF_library-usage_Jan%202023.xlsx"
```

### 6. Checking the connection

```bash
python mongo/scripts/test_connection.py
```

It should print the MongoDB server version.

### 7. Loading the data

```bash
python mongo/scripts/load_data.py
```

This should take about a minute and should end with `patrons: 437115 documents`.

### 8. Creating the indexes

```bash
python mongo/scripts/indexes.py
```

This runs the index experiment and leaves three indexes in place. Run it
after loading, since `load_data.py` drops the collection along with its
indexes.

### 9. (Optional) Running the analysis queries

```bash
python mongo/scripts/queries.py
```

### 10. Running the app

```bash
python mongo/app/main.py
```

## Data design: one collection of embedded documents

In MySQL, I normalized the data into six tables (one patrons table plus five
lookup tables) and used joins to put them back together. In MongoDB, I used a
single `patrons` collection where each document contains everything about
one patron, including the readable names:

```json
{
  "_id": 364974,
  "patron_type": { "code": 0, "name": "Adult" },
  "age_range": { "label": "35 to 44 years", "sort_order": 5 },
  "home_library": { "code": "v3", "branch": "Visitacion Valley" },
  "notification": { "code": "z", "name": "Email" },
  "total_checkouts": 45380,
  "total_renewals": 1234,
  "circulation_active": { "month": "January", "year": 2023 },
  "provided_email": true,
  "within_sf_county": true,
  "year_registered": 2003
}
```

(The age range, renewals, and activity date above are illustrative; the
other values are this patron's actual data.)

Design decisions:

- **Embedding instead of lookup collections.** The lookup values (18 patron
  types, 10 age ranges, 30 branches, 4 contact preferences) are small 
  and are needed every time a patron is read. Embedding them
  means reading a patron is one document lookup with no joins, and the
  analysis queries reach names with dot notation such as
  `$home_library.branch`.
- **The trade-off.** This intentionally gives up the normalization from
  Assignment 1. A branch name like "Visitacion Valley" is now stored in every
  one of that branch's patron documents, so renaming a branch would mean
  updating thousands of documents (one `update_many`) instead of one row.
  Since names rarely change and reads are far more common, embedding fits
  this data.
- **The same IDs as MySQL.** `_id` is the patron's position in the
  spreadsheet (1 to 437,115), the same number as `patron_id` in MySQL, so
  results can be compared patron by patron between the two databases.
- **Missing data is `null`.** As in MySQL, 927 patrons have
  `age_range: null`, 2 have `home_library: null`, and 40,592 have
  `circulation_active: null`.
- **Related fields grouped together.** The activity month and year are one
  `circulation_active` sub-document, since they are always present or
  missing together.
- **Lists of choices come from the data.** Without lookup tables, the app
  builds its lists of patron types, age ranges, branches, and contact
  preferences by grouping the embedded documents with `$group`.

The same cleaning steps from Assignment 1 apply: removing line breaks from
column headers, trimming spaces, converting blank months to `null`, and
converting the activity year from a decimal to a whole number.

### Indexes

| Index | Used by |
|---|---|
| `_id` (automatic) | Looking up, updating, and deleting a patron by ID |
| `year_registered` | Counting patrons by registration year |
| `total_checkouts` | Finding heavy borrowers, and sorting for the app's top borrowers list |
| `home_library.branch` | Counting patrons by branch (an index on a field inside an embedded document) |

## Using the app

| Option | What it does | MongoDB operation |
|---|---|---|
| 1. Looking up a patron | Shows one patron's details | `find_one({"_id": ...})` |
| 2. Show branch statistics | Patron counts and average checkouts per branch, sortable | `aggregate()` with `$match`, `$group`, `$sort` |
| 3. Show top borrowers | The top 1-100 patrons by checkouts | `find().sort().limit()`, using the `total_checkouts` index |
| 4. Adding a new patron | Adds a patron, choosing from lists built from the data | `insert_one()` |
| 5. Updating a patron | Records new checkouts, or changes contact preference or patron type | `update_one()` with `$inc` and `$set` |
| 6. Deleting a patron | Deletes a patron after confirmation | `delete_one()` |
| 7. Quit | Exits the app | |

Design notes:

- **One client for the whole app.** `MongoClient` maintains a pool of
  connections and is created once at startup, rather than once per query
  like the MySQL version's connections.
- **Generating IDs.** MongoDB has no `AUTO_INCREMENT`, so a new patron gets
  the highest existing `_id` plus 1. Because `_id` is always unique, a
  conflicting insert raises `DuplicateKeyError` and the app tries the next
  number. Unlike MySQL, a deleted patron's ID can be reused by the next new
  patron.
- **Updates in place.** `$inc` adds new checkouts inside the database, like
  `SET total_checkouts = total_checkouts + n`, and `$set` replaces a whole
  embedded document (such as the contact preference) in one step.
- **Safe input.** MongoDB queries are Python dictionaries rather than text,
  so there is no SQL to inject into. The equivalent risk is a user inserting
  query operators like `$gt`; the app prevents this by converting all input
  to plain numbers or matching it against fixed lists before it reaches a
  query.
- **No commits.** Each MongoDB write is saved as soon as it succeeds, unlike
  MySQL, where changes needed `conn.commit()`.

## Results

Full results, timings, and the comparison with MySQL are in
[results/README.md](results/README.md). In summary:

- All eight analysis queries return exactly the same results as the MySQL
  version, confirming the migration.
- Inserting all 437,115 documents took 6.0 seconds.
- Indexes made counting queries about 30-38x faster, answered entirely from
  the index (`COUNT_SCAN`, 0 documents examined).
- One query was much less improved than in MySQL (about 4x instead of 14x)
  because MongoDB does not store `_id` in secondary indexes, so it had to
  fetch each matching document.

## MySQL vs. MongoDB

| | MySQL (Assignment 1) | MongoDB (Assignment 2) |
|---|---|---|
| Structure | 6 normalized tables | 1 collection of embedded documents |
| Schema | Defined up front with `CREATE TABLE` | Created on first insert; documents define their own shape |
| Relationships | Foreign keys and joins | Embedded documents and dot notation |
| Data integrity | Foreign keys reject invalid references | Enforced by the app (choices come from fixed lists) |
| Analysis | SQL with `GROUP BY` | Aggregation pipelines |
| Reading one patron | `SELECT` with 5 joins | One `find_one` |
| Renaming a branch | Update one row | Update every patron at that branch |
| IDs | `AUTO_INCREMENT` | Chosen by the app |
| Saving changes | `commit()` | Saved on each write |

## What I've learned

- **Designing for how data is read.** In MySQL, I designed tables to avoid
  repeating data. In MongoDB, I designed documents around how the app reads
  them, accepting repetition so that reading a patron needs no joins.
- **Aggregation pipelines.** Each stage maps closely to part of a SQL query
  (`$match` to `WHERE`, `$group` to `GROUP BY`, `$sort` to `ORDER BY`), but
  thinking of a query as a series of steps made complex queries easier to
  build and test one stage at a time.
- **Indexes behave differently between databases.** The same query was
  fully covered by an index in MySQL but not in MongoDB, because MySQL stores
  the primary key inside every index and MongoDB does not. `explain()` with
  `executionStats` made this visible with exact counts rather than estimates.
- **Indexing embedded fields.** MongoDB can index a field inside an embedded
  document, which replaced what was a two-table join in MySQL.
- **Trade-offs move, not disappear.** MongoDB removed joins and made the
  loading script simpler, but responsibilities MySQL handled automatically,
  such as generating IDs and rejecting invalid references, moved into my
  application code.
- **Installation and storage issues.** Homebrew could not install MongoDB on
  macOS 14, and my disk was nearly full, so I learned to install from
  MongoDB's official download and to diagnose storage problems from the
  command line.

## Acknowledgments

- I used Claude AI throughout this assignment for step-by-step guidance on setting up MongoDB and 
navigating Compass with my computer and setting up the terminal app with the library dataset but 
through MongoDB. Also used Claude in providing help and aid for understanding the code for MongoDB. 
Also provided aid in debugging and creating the app.