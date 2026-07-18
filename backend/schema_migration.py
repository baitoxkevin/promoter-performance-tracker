import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "promoter_tracker.db")

def run_promoters_migration():
    if not os.path.exists(DB_PATH):
        print(f"[Migration] Database file not found at {DB_PATH}. It will be initialized on app startup.")
        return

    print(f"[Migration] Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get existing columns in promoters table
    cursor.execute("PRAGMA table_info(promoters)")
    columns = [col[1] for col in cursor.fetchall()]
    print("[Migration] Existing columns in 'promoters':", columns)

    new_cols = {
        "gender": "TEXT",
        "avatar": "TEXT"
    }

    modified = False
    for col_name, col_type in new_cols.items():
        if col_name not in columns:
            print(f"[Migration] Adding column '{col_name}' ({col_type}) to table 'promoters'...")
            cursor.execute(f"ALTER TABLE promoters ADD COLUMN {col_name} {col_type}")
            modified = True

    if modified:
        conn.commit()
        print("[Migration] Migration completed successfully and changes committed.")
    else:
        print("[Migration] No new columns to add. 'promoters' schema is up to date.")

    conn.close()

if __name__ == "__main__":
    run_promoters_migration()
