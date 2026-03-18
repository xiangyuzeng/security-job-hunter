#!/usr/bin/env python3
"""One-time migration script: copy all jobs from local SQLite to Turso cloud.
Usage:
    export TURSO_DATABASE_URL=libsql://your-db.turso.io
    export TURSO_AUTH_TOKEN=eyJ...
    python migrate_to_turso.py
"""

import os
import sqlite3
import sys

LOCAL_DB = "jobs.db"


def main():
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")

    if not turso_url or not turso_token:
        print("Error: Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment variables.")
        sys.exit(1)

    try:
        import libsql_client
    except ImportError:
        print("Error: pip install libsql-client")
        sys.exit(1)

    if not os.path.exists(LOCAL_DB):
        print(f"Error: Local database '{LOCAL_DB}' not found.")
        sys.exit(1)

    # Read from local SQLite
    local = sqlite3.connect(LOCAL_DB)
    local.row_factory = sqlite3.Row
    rows = local.execute("SELECT * FROM jobs").fetchall()
    print(f"Found {len(rows)} jobs in local database.")

    # Connect to Turso via HTTP client (convert libsql:// to https://)
    turso_url = turso_url.replace("libsql://", "https://")
    client = libsql_client.create_client_sync(url=turso_url, auth_token=turso_token)

    # Create tables
    client.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_url TEXT UNIQUE,
            title TEXT,
            company TEXT,
            company_url TEXT,
            location TEXT,
            is_remote BOOLEAN,
            description TEXT,
            job_type TEXT,
            salary_min REAL,
            salary_max REAL,
            salary_interval TEXT,
            date_posted TEXT,
            source TEXT,
            status TEXT DEFAULT 'new',
            is_favorite INTEGER DEFAULT 0,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    client.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    client.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
    client.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted)")
    client.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Insert jobs
    inserted = 0
    skipped = 0
    for row in rows:
        r = dict(row)
        try:
            client.execute("""
                INSERT INTO jobs (job_url, title, company, company_url, location,
                                  is_remote, description, job_type, salary_min,
                                  salary_max, salary_interval, date_posted, source,
                                  status, is_favorite, first_seen_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                r["job_url"], r["title"], r["company"], r["company_url"],
                r["location"], r["is_remote"], r["description"], r["job_type"],
                r["salary_min"], r["salary_max"], r["salary_interval"],
                r["date_posted"], r["source"], r["status"], r["is_favorite"],
                r["first_seen_at"], r["updated_at"],
            ])
            inserted += 1
        except Exception as e:
            if "UNIQUE" in str(e).upper():
                skipped += 1
            else:
                print(f"Error inserting {r['job_url']}: {e}")

    client.close()
    local.close()

    print(f"Migration complete: {inserted} inserted, {skipped} skipped (duplicates).")


if __name__ == "__main__":
    main()
