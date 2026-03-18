import logging
import re
import sqlite3
from datetime import datetime
from contextlib import contextmanager

import config

logger = logging.getLogger(__name__)

# Try to import libsql_client for Turso cloud support
_use_turso = False
_turso_client = None
_turso_initialized = False


def _get_turso_client():
    """Lazy-initialize Turso client on first use."""
    global _use_turso, _turso_client, _turso_initialized
    if _turso_initialized:
        return _turso_client
    _turso_initialized = True
    if config.TURSO_DATABASE_URL:
        try:
            import libsql_client
            _turso_url = config.TURSO_DATABASE_URL.replace("libsql://", "https://")
            _turso_client = libsql_client.create_client_sync(
                url=_turso_url,
                auth_token=config.TURSO_AUTH_TOKEN,
            )
            _use_turso = True
            logger.info("Using libsql_client for Turso cloud database")
        except ImportError:
            logger.warning("libsql_client not installed, falling back to sqlite3")
    return _turso_client


def _get_sqlite_path():
    """Get writable SQLite path. On Vercel, use /tmp."""
    if config.IS_SERVERLESS and not _use_turso:
        return "/tmp/jobs.db"
    return str(config.DB_PATH)


@contextmanager
def get_db():
    """Yield a connection-like object. For local SQLite, yields a real connection.
    For Turso, yields a wrapper around libsql_client."""
    _get_turso_client()
    if _use_turso:
        yield TursoConnection()
    else:
        conn = sqlite3.connect(_get_sqlite_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


class TursoCursor:
    """Minimal cursor interface wrapping a libsql_client result set."""
    def __init__(self, result_set):
        self._rs = result_set
        self.description = [(col, None, None, None, None, None, None) for col in result_set.columns] if result_set.columns else []

    def fetchall(self):
        return self._rs.rows

    def fetchone(self):
        return self._rs.rows[0] if self._rs.rows else None


class TursoConnection:
    """Minimal connection-like wrapper around libsql_client.
    Supports execute() and commit() to match sqlite3 interface."""

    def execute(self, sql, params=None):
        # libsql_client uses positional args
        if params:
            rs = _turso_client.execute(sql, list(params))
        else:
            rs = _turso_client.execute(sql)
        return TursoCursor(rs)

    def commit(self):
        pass  # libsql_client auto-commits

    def close(self):
        pass


def _rows_to_dicts(cursor):
    """Convert cursor results to list of dicts."""
    if _use_turso:
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    else:
        return [dict(r) for r in cursor.fetchall()]


def _fetchone_value(cursor, idx=0):
    """Fetch one row and return a single column value."""
    row = cursor.fetchone()
    if row is None:
        return None
    if _use_turso:
        return row[idx]
    else:
        return row[idx]


def init_db():
    with get_db() as conn:
        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


def set_metadata(key, value):
    """Store a key-value pair in the metadata table."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, str(value)),
        )


def get_metadata(key, default=None):
    """Retrieve a value from the metadata table."""
    with get_db() as conn:
        cursor = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is None:
            return default
        return row[0] if _use_turso else row["value"]


def upsert_jobs(jobs_df):
    """Insert new jobs from a pandas DataFrame. Returns count of newly inserted jobs."""
    if jobs_df is None or jobs_df.empty:
        return 0

    new_count = 0
    with get_db() as conn:
        for _, row in jobs_df.iterrows():
            job_url = str(row.get("job_url", ""))
            if not job_url:
                continue
            try:
                conn.execute("""
                    INSERT INTO jobs (job_url, title, company, company_url, location,
                                     is_remote, description, job_type, salary_min,
                                     salary_max, salary_interval, date_posted, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_url,
                    _safe_str(row.get("title")),
                    _safe_str(row.get("company")),
                    _safe_str(row.get("company_url")),
                    _safe_str(row.get("location")),
                    bool(row.get("is_remote", False)),
                    _safe_str(row.get("description")),
                    _safe_str(row.get("job_type")),
                    _safe_float(row.get("min_amount")),
                    _safe_float(row.get("max_amount")),
                    _safe_str(row.get("interval")),
                    _safe_str(row.get("date_posted")),
                    _safe_str(row.get("site")),
                ))
                new_count += 1
            except Exception as e:
                if "UNIQUE constraint" in str(e) or "UNIQUE" in str(e).upper():
                    pass  # duplicate job_url, skip
                else:
                    logger.error(f"Error inserting job {job_url}: {e}")
    return new_count


def _safe_str(val):
    if val is None:
        return ""
    s = str(val)
    if s in ("nan", "None", "NaT", "<NA>"):
        return ""
    return s


def _safe_float(val):
    try:
        if val is None or str(val) in ("", "nan", "None"):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None


def get_jobs(status=None, source=None, favorite_only=False, search=None,
             sort_by="date_posted", sort_order="desc", limit=200, offset=0):
    """Query jobs with optional filters. Defaults to last 14 days."""
    conditions = []
    params = []

    # Always filter to recent 14 days for display
    conditions.append("date_posted >= date('now', '-14 days')")

    # Exclude irrelevant titles at SQL level (simple LIKE patterns)
    _sql_exclude = [
        "%software engineer%", "%frontend%", "%backend%",
        "%full stack%", "%fullstack%", "%data scientist%",
        "%marketing%", "%sales%", "%dba%", "%database admin%",
        "%help desk%", "%graphic design%",
        "%product manager%", "%scrum master%", "%recruiter%",
        "%ui/ux%", "%uiux%", "%web developer%",
    ]
    for pattern in _sql_exclude:
        conditions.append("LOWER(title) NOT LIKE ?")
        params.append(pattern)

    # Only show jobs with titles relevant to Security/Cybersecurity
    _relevant_keywords = [
        "security", "cybersecurity", "infosec", "soc", "siem",
        "threat", "vulnerability", "penetration", "pentest",
        "incident", "compliance", "grc", "risk", "audit",
        "forensics", "malware", "firewall", "ids", "ips",
        "zero trust", "devsecops", "ciso", "nist", "encryption",
        "identity", "access", "iam", "appsec", "red team",
        "blue team", "endpoint", "analyst", "engineer",
        "architect", "operations",
    ]
    relevance_conditions = [f"LOWER(title) LIKE ?" for _ in _relevant_keywords]
    conditions.append("(" + " OR ".join(relevance_conditions) + ")")
    params.extend([f"%{kw}%" for kw in _relevant_keywords])

    if status and status != "all":
        conditions.append("status = ?")
        params.append(status)

    if source and source != "all":
        conditions.append("source = ?")
        params.append(source)

    if favorite_only:
        conditions.append("is_favorite = 1")

    if search:
        conditions.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    allowed_sort = {"date_posted", "title", "company", "salary_min", "first_seen_at", "source"}
    if sort_by not in allowed_sort:
        sort_by = "date_posted"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    query = f"""
        SELECT * FROM jobs {where}
        ORDER BY {sort_by} {sort_order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with get_db() as conn:
        cursor = conn.execute(query, params)
        return _rows_to_dicts(cursor)


def update_job_status(job_id, status):
    valid = {"new", "seen", "applied", "hidden"}
    if status not in valid:
        return False
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, job_id)
        )
    return True


def toggle_favorite(job_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET is_favorite = 1 - is_favorite, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job_id,)
        )
    return True


def get_stats():
    with get_db() as conn:
        total = _fetchone_value(conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE date_posted >= date('now', '-14 days')"))
        new = _fetchone_value(conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'new' AND date_posted >= date('now', '-14 days')"))
        applied = _fetchone_value(conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'applied'"))
        favorites = _fetchone_value(conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE is_favorite = 1"))

        today = datetime.now().strftime("%Y-%m-%d")
        new_today = _fetchone_value(conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE DATE(first_seen_at) = ?", (today,)))

        cursor = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM jobs WHERE date_posted >= date('now', '-14 days') GROUP BY source ORDER BY cnt DESC"
        )
        if _use_turso:
            sources = {row[0]: row[1] for row in cursor.fetchall()}
        else:
            sources = {r["source"]: r["cnt"] for r in cursor.fetchall()}

        return {
            "total": total or 0,
            "new": new or 0,
            "applied": applied or 0,
            "favorites": favorites or 0,
            "new_today": new_today or 0,
            "by_source": sources,
        }


def get_new_jobs_since(timestamp):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM jobs WHERE first_seen_at > ? ORDER BY first_seen_at DESC",
            (timestamp,)
        )
        return _rows_to_dicts(cursor)
