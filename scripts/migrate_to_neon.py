"""
scripts/migrate_to_neon.py — one-time move of existing local data into Neon.

Run this ONCE, after DATABASE_URL is set in your .env, from a machine with
normal internet access (this can't be run inside a network-isolated sandbox
— it needs a real route to your Neon endpoint). It:

  1. Reads every (client_id, key, value, updated_at) row out of the local
     data/app.db SQLite file (the client_data table core/db.py has always
     used).
  2. Connects to the Neon Postgres database named by DATABASE_URL and
     upserts every row into its client_data table (same schema, created
     automatically the first time core/db.py connects — this script also
     ensures it directly, so it works even before the app has run once
     against Neon).
  3. Leaves data/app.db untouched on disk — nothing is deleted. If
     anything goes wrong, or you want to keep testing locally without
     Neon, just unset DATABASE_URL in .env and the app goes right back to
     reading/writing the SQLite file, unaffected by this script ever
     having run.

It does NOT touch activity_log or market_data_cache — those are new
tables with no local history to carry over (activity_log didn't exist
before this feature; market_data_cache only ever holds a refreshable
cache, not anything worth preserving).

Usage:
    python scripts/migrate_to_neon.py
    python scripts/migrate_to_neon.py --dry-run   # show what would move, write nothing
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.security import get_database_url  # noqa: E402

SQLITE_PATH = os.path.join("data", "app.db")


def main():
    dry_run = "--dry-run" in sys.argv

    database_url = get_database_url()
    if not database_url:
        print("ERROR: DATABASE_URL is not set in .env. Add it (Neon dashboard -> "
              "your project -> Connection Details -> Connection string) and re-run.")
        sys.exit(1)

    if not os.path.exists(SQLITE_PATH):
        print(f"No local database found at {SQLITE_PATH} — nothing to migrate. "
              "(This is expected if you've never run the app without DATABASE_URL set.)")
        return

    import psycopg2
    from psycopg2.extras import Json
    import json

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    rows = sqlite_conn.execute(
        "SELECT client_id, key, value, updated_at FROM client_data ORDER BY client_id, key"
    ).fetchall()
    sqlite_conn.close()

    print(f"Found {len(rows)} row(s) in local {SQLITE_PATH}.")
    if not rows:
        return

    for client_id, key, _value, updated_at in rows:
        print(f"  {client_id:<10} {key:<40} (last updated {updated_at})")

    if dry_run:
        print("\n--dry-run: no changes written to Neon.")
        return

    pg_conn = psycopg2.connect(database_url)
    pg_conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS client_data (
            client_id  TEXT NOT NULL,
            key        TEXT NOT NULL,
            value      JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (client_id, key)
        );
    """)
    pg_conn.commit()

    migrated, skipped = 0, 0
    with pg_conn.cursor() as cur:
        for client_id, key, value, updated_at in rows:
            try:
                parsed = json.loads(value)
            except Exception as e:
                print(f"  SKIPPED {client_id}/{key} — couldn't parse stored JSON: {e}")
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO client_data (client_id, key, value, updated_at) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (client_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
                (client_id, key, Json(parsed, dumps=lambda d: json.dumps(d, default=str)), updated_at),
            )
            migrated += 1
    pg_conn.commit()
    pg_conn.close()

    print(f"\nDone. Migrated {migrated} row(s) to Neon" + (f", skipped {skipped}." if skipped else "."))
    print("data/app.db was left untouched — safe to keep as a local backup.")


if __name__ == "__main__":
    main()
