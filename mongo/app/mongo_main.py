import sys, os
MONGO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(MONGO_DIR)

from datetime import date

from pymongo import MongoClient
from pymongo.errors import PyMongoError, DuplicateKeyError
from config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
patrons = client[DB_NAME].patrons

# Input helpers
def ask_int(prompt):
    """Keep asking until the user types a whole number.
    Returns None if they just press Enter."""
    while True:
        text = input(prompt).strip()
        if text == "":
            return None
        if text.isdigit():
            return int(text)
        print("Please enter a whole number (or press Enter to cancel).")

def ask_yes_no(prompt):
    """Keep asking until the user types y or n. Returns True for yes."""
    while True:
        answer = input(prompt + " (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please type y or n.")

def choose_option(title, options, allow_blank=False):
    """Show a list of (key, label) pairs and return the key the user picks,
    as a string. If allow_blank is True, pressing Enter returns None."""
    print(f"\n{title}")
    for key, label in options:
        print(f"  {key}. {label}")
    valid_keys = {str(key) for key, label in options}

    prompt = "Choose one (or press Enter to skip): " if allow_blank else "Choose one: "
    while True:
        choice = input(prompt).strip()
        if choice == "" and allow_blank:
            return None
        if choice in valid_keys:
            return choice
        print("Not a valid choice, try again.")

# Lists of choices, built from the data itself
def get_patron_types():
    results = patrons.aggregate([
        {"$group": {"_id": "$patron_type"}},
        {"$sort": {"_id.code": 1}},
    ])
    return [r["_id"] for r in results]          

def get_age_ranges():
    results = patrons.aggregate([
        {"$match": {"age_range": {"$ne": None}}},
        {"$group": {"_id": "$age_range"}},
        {"$sort": {"_id.sort_order": 1}},
    ])
    return [r["_id"] for r in results]          

def get_branches():
    results = patrons.aggregate([
        {"$match": {"home_library": {"$ne": None}}},
        {"$group": {"_id": "$home_library.branch", "codes": {"$addToSet": "$home_library.code"}}},
        {"$sort": {"_id": 1}},
    ])
    return [{"branch": r["_id"], "code": min(r["codes"], key=lambda c: (len(c), c))}
            for r in results]

def get_notifications():
    results = patrons.aggregate([
        {"$group": {"_id": "$notification"}},
        {"$sort": {"_id.name": 1}},
    ])
    return [r["_id"] for r in results]         

def pick_patron_type(title):
    types = get_patron_types()
    choice = choose_option(title, [(t["code"], t["name"]) for t in types])
    return next(t for t in types if str(t["code"]) == choice)

def pick_notification(title):
    notifications = get_notifications()
    choice = choose_option(title, [(n["code"], n["name"]) for n in notifications])
    return next(n for n in notifications if n["code"] == choice)

# Menu option 1: look up a patron
def look_up_patron():
    patron_id = ask_int("Enter patron ID (or press Enter to go back): ")
    if patron_id is None:
        return

    doc = patrons.find_one({"_id": patron_id})
    if doc is None:
        print(f"No patron found with ID {patron_id}.")
        return

    age = doc["age_range"]["label"] if doc.get("age_range") else "Unknown"
    library = doc.get("home_library")
    branch = f"{library['branch']} ({library['code']})" if library else "Unknown (no code)"
    active = doc.get("circulation_active")
    last_active = f"{active['month']} {active['year']}" if active else "Never"

    print(f"\n--- Patron {doc['_id']} ---")
    print(f"Type:               {doc['patron_type']['name']}")
    print(f"Age range:          {age}")
    print(f"Home branch:        {branch}")
    print(f"Contact preference: {doc['notification']['name']}")
    print(f"Total checkouts:    {doc['total_checkouts']}")
    print(f"Total renewals:     {doc['total_renewals']}")
    print(f"Last active:        {last_active}")
    print(f"Provided email:     {'Yes' if doc['provided_email'] else 'No'}")
    print(f"Lives in SF:        {'Yes' if doc['within_sf_county'] else 'No'}")
    print(f"Registered:         {doc['year_registered']}")

#  Menu option 2: branch statistics
def show_branch_statistics():
    print("\nSort branches by:")
    print("1. Number of patrons")
    print("2. Average checkouts")
    choice = input("Choose 1 or 2 (or press Enter for 1): ").strip()

    sort_options = {
        "": {"patrons": -1},
        "1": {"patrons": -1},
        "2": {"avg_checkouts": -1},
    }
    if choice not in sort_options:
        print("Invalid choice.")
        return

    results = patrons.aggregate([
        {"$match": {"home_library": {"$ne": None}}},
        {"$group": {
            "_id": "$home_library.branch",
            "patrons": {"$sum": 1},
            "avg_checkouts": {"$avg": "$total_checkouts"},
        }},
        {"$sort": sort_options[choice]},
    ])

    print(f"\n{'Branch':<20}{'Patrons':>10}{'Avg checkouts':>16}")
    print("-" * 46)
    for r in results:
        print(f"{r['_id']:<20}{r['patrons']:>10,}{r['avg_checkouts']:>16.1f}")

# Menu option 3: top borrowers 
def show_top_borrowers():
    limit = ask_int("How many top borrowers to show? (1-100, press Enter for 10): ")
    if limit is None:
        limit = 10
    if limit < 1 or limit > 100:
        print("Please choose a number from 1 to 100.")
        return

    cursor = (patrons
              .find({}, {"patron_type.name": 1, "home_library.branch": 1,
                         "total_checkouts": 1, "year_registered": 1})
              .sort("total_checkouts", -1)
              .limit(limit))

    print(f"\n{'Rank':<6}{'Patron ID':<11}{'Type':<16}{'Branch':<20}{'Checkouts':>10}{'Registered':>12}")
    print("-" * 75)
    for rank, doc in enumerate(cursor, start=1):
        branch = doc["home_library"]["branch"] if doc.get("home_library") else "Unknown"
        print(f"{rank:<6}{doc['_id']:<11}{doc['patron_type']['name']:<16}{branch:<20}"
              f"{doc['total_checkouts']:>10,}{doc['year_registered']:>12}")


# Menu option 4: addding a new patron
def add_new_patron():
    patron_type = pick_patron_type("Patron type:")

    ages = get_age_ranges()
    age_choice = choose_option("Age range:", [(a["sort_order"], a["label"]) for a in ages],
                               allow_blank=True)
    age_range = next((a for a in ages if str(a["sort_order"]) == age_choice), None)

    branches = get_branches()
    branch_choice = choose_option("Home branch:",
                                  [(i, b["branch"]) for i, b in enumerate(branches, start=1)],
                                  allow_blank=True)
    home_library = branches[int(branch_choice) - 1] if branch_choice else None

    notification = pick_notification("Contact preference:")
    provided_email = ask_yes_no("\nDid they provide an email address?")
    within_sf = ask_yes_no("Do they live in San Francisco County?")

    if not ask_yes_no("\nSave this new patron?"):
        print("Cancelled. Nothing was saved.")
        return

    new_patron = {
        "patron_type": patron_type,
        "age_range": age_range,
        "home_library": home_library,
        "notification": notification,
        "total_checkouts": 0,
        "total_renewals": 0,
        "circulation_active": None,
        "provided_email": provided_email,
        "within_sf_county": within_sf,
        "year_registered": date.today().year,
    }

    highest = patrons.find_one(sort=[("_id", -1)], projection={"_id": 1})
    new_id = highest["_id"] + 1 if highest else 1
    while True:
        try:
            patrons.insert_one({"_id": new_id, **new_patron})
            break
        except DuplicateKeyError:
            new_id += 1

    print(f"Saved! The new patron's ID is {new_id}.")

# Menu option 5: updating a patron
def update_patron():
    patron_id = ask_int("Enter the ID of the patron to update (or press Enter to go back): ")
    if patron_id is None:
        return

    doc = patrons.find_one({"_id": patron_id}, {"total_checkouts": 1})
    if doc is None:
        print(f"No patron found with ID {patron_id}.")
        return

    print(f"\nPatron {patron_id} currently has {doc['total_checkouts']:,} checkouts.")
    print("What would you like to update?")
    print("1. Record new checkouts")
    print("2. Change contact preference")
    print("3. Change patron type")
    choice = input("Choose 1-3 (or press Enter to cancel): ").strip()

    if choice == "":
        return
    elif choice == "1":
        count = ask_int("How many new checkouts? ")
        if not count:
            print("Nothing changed.")
            return
        today = date.today()
        changes = {
            "$inc": {"total_checkouts": count},
            "$set": {"circulation_active": {"month": today.strftime("%B"), "year": today.year}},
        }
    elif choice == "2":
        changes = {"$set": {"notification": pick_notification("New contact preference:")}}
    elif choice == "3":
        changes = {"$set": {"patron_type": pick_patron_type("New patron type:")}}
    else:
        print("Invalid choice. Nothing changed.")
        return

    result = patrons.update_one({"_id": patron_id}, changes)
    if result.modified_count == 1:
        print("Updated! Use option 1 to see the patron's new details.")
    else:
        print("Nothing was changed (the new value was the same as the old one).")

# Menu option 6: deleting a patron
def delete_patron():
    patron_id = ask_int("Enter the ID of the patron to delete (or press Enter to go back): ")
    if patron_id is None:
        return

    doc = patrons.find_one({"_id": patron_id})
    if doc is None:
        print(f"No patron found with ID {patron_id}.")
        return

    print(f"\nPatron {doc['_id']}: {doc['patron_type']['name']}, "
          f"{doc['total_checkouts']:,} checkouts, registered {doc['year_registered']}")
    if not ask_yes_no("Are you sure you want to permanently delete this patron?"):
        print("Cancelled. Nothing was deleted.")
        return

    patrons.delete_one({"_id": patron_id})
    print(f"Patron {patron_id} was deleted.")

# Main menu
def main():
    actions = {
        "1": look_up_patron,
        "2": show_branch_statistics,
        "3": show_top_borrowers,
        "4": add_new_patron,
        "5": update_patron,
        "6": delete_patron,
    }

    while True:
        print("\nSan Francisco Public Library System (MongoDB)")
        print("1. Look up a patron")
        print("2. Show branch statistics")
        print("3. Show top borrowers")
        print("4. Add a new patron")
        print("5. Update a patron")
        print("6. Delete a patron")
        print("7. Quit")
        choice = input("Choose an option (1-7): ").strip()

        if choice == "7":
            print("See ya!")
            break
        elif choice in actions:
            try:
                actions[choice]()
            except PyMongoError as err:
                print(f"Database error: {err}")
        else:
            print("Invalid choice. Please enter a number from 1 to 7.")

    client.close()


if __name__ == "__main__":
    main()