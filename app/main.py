import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date

import mysql.connector
from config import DB_CONFIG


# Helpers

def get_connection():
    """Open a new connection to the sfils database."""
    return mysql.connector.connect(**DB_CONFIG)


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

    if allow_blank:
        prompt = "Choose one (or press Enter to skip): "
    else:
        prompt = "Choose one: "

    while True:
        choice = input(prompt).strip()
        if choice == "" and allow_blank:
            return None
        if choice in valid_keys:
            return choice
        print("Not a valid choice, try again.")


# MENU OPTION 1: look up a patron 

def look_up_patron():
    patron_id = ask_int("Enter patron ID (or press Enter to go back): ")
    if patron_id is None:
        return

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.patron_id, pt.patron_type_name, a.age_range_label,
               b.branch_name, p.home_library_code, n.notification_name,
               p.total_checkouts, p.total_renewals,
               p.active_month, p.active_year,
               p.provided_email, p.within_sf_county, p.year_registered
        FROM patrons p
        JOIN patron_types pt ON p.patron_type_code = pt.patron_type_code
        JOIN notification_preferences n ON p.notification_code = n.notification_code
        LEFT JOIN age_ranges a ON p.age_range_id = a.age_range_id
        LEFT JOIN library_codes lc ON p.home_library_code = lc.library_code
        LEFT JOIN branches b ON lc.branch_id = b.branch_id
        WHERE p.patron_id = %s
    """, (patron_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is None:
        print(f"No patron found with ID {patron_id}.")
        return

    if row["active_year"]:
        last_active = f"{row['active_month']} {row['active_year']}"
    else:
        last_active = "Never"

    print(f"\n--- Patron {row['patron_id']} ---")
    print(f"Type:               {row['patron_type_name']}")
    print(f"Age range:          {row['age_range_label'] or 'Unknown'}")
    print(f"Home branch:        {row['branch_name'] or 'Unknown'} ({row['home_library_code'] or 'no code'})")
    print(f"Contact preference: {row['notification_name']}")
    print(f"Total checkouts:    {row['total_checkouts']}")
    print(f"Total renewals:     {row['total_renewals']}")
    print(f"Last active:        {last_active}")
    print(f"Provided email:     {'Yes' if row['provided_email'] else 'No'}")
    print(f"Lives in SF:        {'Yes' if row['within_sf_county'] else 'No'}")
    print(f"Registered:         {row['year_registered']}")


# MENU OPTION 2: branch statistics

def show_branch_statistics():
    print("\nSort branches by:")
    print("1. Number of patrons")
    print("2. Average checkouts")
    choice = input("Choose 1 or 2 (or press Enter for 1): ").strip()

    # Column names can't be passed as %s placeholders, so the user picks
    # from a fixed set of safe options instead of typing SQL directly.
    sort_options = {
        "": "patrons DESC",
        "1": "patrons DESC",
        "2": "avg_checkouts DESC",
    }
    if choice not in sort_options:
        print("Invalid choice.")
        return
    order_by = sort_options[choice]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"""
        SELECT b.branch_name,
               COUNT(*) AS patrons,
               ROUND(AVG(p.total_checkouts), 1) AS avg_checkouts
        FROM patrons p
        JOIN library_codes lc ON p.home_library_code = lc.library_code
        JOIN branches b ON lc.branch_id = b.branch_id
        GROUP BY b.branch_name
        ORDER BY {order_by}
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"\n{'Branch':<20}{'Patrons':>10}{'Avg checkouts':>16}")
    print("-" * 46)
    for row in rows:
        print(f"{row['branch_name']:<20}{row['patrons']:>10,}{row['avg_checkouts']:>16}")


# MENU OPTION 3: top borrowers

def show_top_borrowers():
    limit = ask_int("How many top borrowers to show? (1-100, press Enter for 10): ")
    if limit is None:
        limit = 10
    if limit < 1 or limit > 100:
        print("Please choose a number from 1 to 100.")
        return

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.patron_id, pt.patron_type_name, b.branch_name,
               p.total_checkouts, p.year_registered
        FROM patrons p
        JOIN patron_types pt ON p.patron_type_code = pt.patron_type_code
        LEFT JOIN library_codes lc ON p.home_library_code = lc.library_code
        LEFT JOIN branches b ON lc.branch_id = b.branch_id
        ORDER BY p.total_checkouts DESC
        LIMIT %s
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"\n{'Rank':<6}{'Patron ID':<11}{'Type':<16}{'Branch':<20}{'Checkouts':>10}{'Registered':>12}")
    print("-" * 75)
    for rank, row in enumerate(rows, start=1):
        branch = row["branch_name"] or "Unknown"
        print(f"{rank:<6}{row['patron_id']:<11}{row['patron_type_name']:<16}{branch:<20}"
              f"{row['total_checkouts']:>10,}{row['year_registered']:>12}")


# MENU OPTION 4: add a new patron
def add_new_patron():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT patron_type_code, patron_type_name FROM patron_types ORDER BY patron_type_code")
        patron_type_code = int(choose_option("Patron type:", cursor.fetchall()))

        cursor.execute("SELECT age_range_id, age_range_label FROM age_ranges ORDER BY sort_order")
        age_choice = choose_option("Age range:", cursor.fetchall(), allow_blank=True)
        age_range_id = int(age_choice) if age_choice else None

        cursor.execute("SELECT branch_id, branch_name FROM branches ORDER BY branch_name")
        branch_choice = choose_option("Home branch:", cursor.fetchall(), allow_blank=True)
        library_code = None
        if branch_choice:
            # A branch can have several codes; use its shortest (main) code.
            cursor.execute("""
                SELECT library_code FROM library_codes
                WHERE branch_id = %s
                ORDER BY LENGTH(library_code), library_code
                LIMIT 1
            """, (int(branch_choice),))
            library_code = cursor.fetchone()[0]

        cursor.execute("SELECT notification_code, notification_name FROM notification_preferences ORDER BY notification_name")
        notification_code = choose_option("Contact preference:", cursor.fetchall())

        provided_email = ask_yes_no("\nDid they provide an email address?")
        within_sf = ask_yes_no("Do they live in San Francisco County?")
        year_registered = date.today().year

        if not ask_yes_no("\nSave this new patron?"):
            print("Cancelled. Nothing was saved.")
            return

        cursor.execute("""
            INSERT INTO patrons (
                patron_type_code, age_range_id, home_library_code, notification_code,
                total_checkouts, total_renewals, active_month, active_year,
                provided_email, within_sf_county, year_registered
            ) VALUES (%s, %s, %s, %s, 0, 0, NULL, NULL, %s, %s, %s)
        """, (patron_type_code, age_range_id, library_code, notification_code,
              provided_email, within_sf, year_registered))
        conn.commit()
        print(f"Saved! The new patron's ID is {cursor.lastrowid}.")
    finally:
        cursor.close()
        conn.close()


# MENU OPTION 5: update a patron

def update_patron():
    patron_id = ask_int("Enter the ID of the patron to update (or press Enter to go back): ")
    if patron_id is None:
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT total_checkouts FROM patrons WHERE patron_id = %s", (patron_id,))
        row = cursor.fetchone()
        if row is None:
            print(f"No patron found with ID {patron_id}.")
            return

        print(f"\nPatron {patron_id} currently has {row[0]:,} checkouts.")
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
            cursor.execute("""
                UPDATE patrons
                SET total_checkouts = total_checkouts + %s,
                    active_month = %s,
                    active_year = %s
                WHERE patron_id = %s
            """, (count, today.strftime("%B"), today.year, patron_id))
        elif choice == "2":
            cursor.execute("SELECT notification_code, notification_name FROM notification_preferences ORDER BY notification_name")
            code = choose_option("New contact preference:", cursor.fetchall())
            cursor.execute("UPDATE patrons SET notification_code = %s WHERE patron_id = %s",
                           (code, patron_id))
        elif choice == "3":
            cursor.execute("SELECT patron_type_code, patron_type_name FROM patron_types ORDER BY patron_type_code")
            new_type = int(choose_option("New patron type:", cursor.fetchall()))
            cursor.execute("UPDATE patrons SET patron_type_code = %s WHERE patron_id = %s",
                           (new_type, patron_id))
        else:
            print("Invalid choice. Nothing changed.")
            return

        conn.commit()
        print("Updated! Use option 1 to see the patron's new details.")
    finally:
        cursor.close()
        conn.close()


# MENU OPTION 6: delete a patron

def delete_patron():
    patron_id = ask_int("Enter the ID of the patron to delete (or press Enter to go back): ")
    if patron_id is None:
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT p.patron_id, pt.patron_type_name, p.total_checkouts, p.year_registered
            FROM patrons p
            JOIN patron_types pt ON p.patron_type_code = pt.patron_type_code
            WHERE p.patron_id = %s
        """, (patron_id,))
        row = cursor.fetchone()
        if row is None:
            print(f"No patron found with ID {patron_id}.")
            return

        print(f"\nPatron {row[0]}: {row[1]}, {row[2]:,} checkouts, registered {row[3]}")
        if not ask_yes_no("Are you sure you want to permanently delete this patron?"):
            print("Cancelled. Nothing was deleted.")
            return

        cursor.execute("DELETE FROM patrons WHERE patron_id = %s", (patron_id,))
        conn.commit()
        print(f"Patron {patron_id} was deleted.")
    finally:
        cursor.close()
        conn.close()


# MAIN MENU

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
        print("\n=== San Francisco Public Library System ===")
        print("1. Look up a patron")
        print("2. Show branch statistics")
        print("3. Show top borrowers")
        print("4. Add a new patron")
        print("5. Update a patron")
        print("6. Delete a patron")
        print("7. Exit")
        choice = input("Choose an option (1-7): ").strip()

        if choice == "7":
            print("Thanks for checking us out!")
            break
        elif choice in actions:
            try:
                actions[choice]()
            except mysql.connector.Error as err:
                print(f"Database error: {err}")
        else:
            print("Invalid choice. Please enter a number from 1 to 7.")


if __name__ == "__main__":
    main()