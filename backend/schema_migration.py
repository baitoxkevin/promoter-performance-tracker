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

def run_submissions_migration():
    if not os.path.exists(DB_PATH):
        print(f"[Migration] Database file not found at {DB_PATH}. It will be initialized on app startup.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    modified = False

    # submissions: full_name + member_id + event
    cursor.execute("PRAGMA table_info(submissions)")
    columns = [col[1] for col in cursor.fetchall()]
    for col_name in ("full_name", "member_id", "event"):
        if col_name not in columns:
            print(f"[Migration] Adding column '{col_name}' (TEXT) to table 'submissions'...")
            cursor.execute(f"ALTER TABLE submissions ADD COLUMN {col_name} TEXT")
            modified = True

    # valid_usernames: member_id + unique index (NULLs don't collide in SQLite)
    cursor.execute("PRAGMA table_info(valid_usernames)")
    columns = [col[1] for col in cursor.fetchall()]
    if "member_id" not in columns:
        print("[Migration] Adding column 'member_id' (TEXT) to table 'valid_usernames'...")
        cursor.execute("ALTER TABLE valid_usernames ADD COLUMN member_id TEXT")
        modified = True
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_valid_member_id ON valid_usernames(member_id)")

    if modified:
        conn.commit()
        print("[Migration] submissions/valid_usernames migration completed.")
    else:
        conn.commit()
        print("[Migration] No new columns to add. 'submissions'/'valid_usernames' schema is up to date.")

    conn.close()


def run_valid_usernames_rebuild():
    """
    Rebuild valid_usernames so member_id is the unique key and usernames may
    repeat. The old schema had UNIQUE(username), which wrongly blocked two
    different people who share a name (e.g. two "Siang"s with different member IDs).
    """
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table missing (fresh DB) → create_all already built the new schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='valid_usernames'")
    if not cursor.fetchone():
        conn.close()
        return
    # Marker: our partial index exists → already migrated
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_valid_username_noid'")
    if cursor.fetchone():
        conn.close()
        return

    print("[Migration] Rebuilding valid_usernames (member_id is the unique key; usernames may repeat)...")
    cursor.executescript(
        """
        PRAGMA foreign_keys=OFF;
        BEGIN;
        CREATE TABLE valid_usernames_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) NOT NULL,
            member_id VARCHAR(50),
            submission_id INTEGER NOT NULL,
            promoter_id INTEGER NOT NULL,
            created_at DATETIME
        );
        INSERT INTO valid_usernames_new (id, username, member_id, submission_id, promoter_id, created_at)
            SELECT id, username, member_id, submission_id, promoter_id, created_at FROM valid_usernames;
        DROP TABLE valid_usernames;
        ALTER TABLE valid_usernames_new RENAME TO valid_usernames;
        CREATE UNIQUE INDEX idx_valid_member_id ON valid_usernames(member_id);
        CREATE UNIQUE INDEX idx_valid_username_noid ON valid_usernames(username) WHERE member_id IS NULL;
        COMMIT;
        PRAGMA foreign_keys=ON;
        """
    )
    conn.commit()
    conn.close()
    print("[Migration] valid_usernames rebuild complete.")


if __name__ == "__main__":
    run_promoters_migration()
    run_submissions_migration()
    run_valid_usernames_rebuild()
