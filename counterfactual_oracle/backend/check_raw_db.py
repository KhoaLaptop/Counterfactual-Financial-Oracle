import sqlite3
import os

# Find the database file
db_path = "counterfactual.db"
if not os.path.exists(db_path):
    print(f"Database file {db_path} not found in current directory.")
    # Try to find it from .env or guess
    print("Listing files:")
    print(os.listdir("."))
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM reports")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} rows in reports table:")
    for row in rows:
        print(f"ID: {row[0]} (Type: {type(row[0])})")
    conn.close()
