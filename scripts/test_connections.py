import sys, os

# Let this script find config.py, which is one folder up
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from config import DB_CONFIG

# Open a connection using the settings in config.py
conn = mysql.connector.connect(**DB_CONFIG)

# Ask MySQL which database we're using
cursor = conn.cursor()
cursor.execute("SELECT DATABASE();")
print("Connected to:", cursor.fetchone()[0])

conn.close()