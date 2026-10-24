import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from config import DB_CONFIG


# Helpers

def get_connection():
    """Open a new connection to the sfils database."""
    return mysql.connector.connect(**DB_CONFIG)


def ask_int(prompt):
    """Keep asking until the user types a whole number.
    Returns None if they just press Enter (to cancel)."""
    while True:
        text = input(prompt).strip()
        if text == "":
            return None
        if text.isdigit():
            return int(text)
        print("Please enter a whole number (or press Enter to cancel).")


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

# MAIN MENU

def not_built_yet():
    print("This option isn't built yet.")


def main():
    actions = {
        "1": look_up_patron,
        "2": show_branch_statistics,
        "3": show_top_borrowers,
        "4": not_built_yet,
        "5": not_built_yet,
        "6": not_built_yet,
    }

    while True:
        print("\n=== San Francisco Public Library System ===")
        print("1. Look up a patron")
        print("2. Show branch statistics")
        print("3. Show top borrowers")
        print("4. Add a new patron")
        print("5. Update a patron")
        print("6. Delete a patron")
        print("7. Quit")
        choice = input("Choose an option (1-7): ").strip()

        if choice == "7":
            print("Goodbye!")
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