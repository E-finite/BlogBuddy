"""Database initialization and utilities."""
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import config


def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(config.APP_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Sites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id TEXT PRIMARY KEY,
            wp_base_url TEXT NOT NULL,
            wp_username TEXT NOT NULL,
            wp_app_password_enc TEXT NOT NULL,
            default_author_id INTEGER NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            result_json TEXT,
            error_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Job steps table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            step TEXT NOT NULL,
            status TEXT NOT NULL,
            detail_json TEXT,
            ts TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    # Scraped pages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id TEXT NOT NULL,
            url TEXT NOT NULL,
            canonical_url TEXT,
            title TEXT,
            clean_text TEXT,
            headings_json TEXT,
            html_snippet TEXT,
            status_code INTEGER,
            fetched_at TEXT NOT NULL,
            content_hash TEXT,
            page_type TEXT,
            FOREIGN KEY (site_id) REFERENCES sites(id),
            UNIQUE(site_id, url)
        )
    """)

    # Page chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER NOT NULL,
            site_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            section_heading TEXT,
            chunk_text TEXT NOT NULL,
            chunk_tokens INTEGER,
            url TEXT,
            FOREIGN KEY (page_id) REFERENCES scraped_pages(id),
            FOREIGN KEY (site_id) REFERENCES sites(id)
        )
    """)

    # Site DNA table (brand identity extracted from website)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_dna (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id TEXT NOT NULL,
            brand_summary TEXT,
            target_audiences_json TEXT,
            pain_points_json TEXT,
            solutions_themes_json TEXT,
            tone_keywords_json TEXT,
            avoid_words_json TEXT,
            proof_points_json TEXT,
            compliance_notes_json TEXT,
            generated_at TEXT NOT NULL,
            source_pages_json TEXT,
            FOREIGN KEY (site_id) REFERENCES sites(id)
        )
    """)

    # Create indexes for performance
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_page_chunks_site ON page_chunks(site_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scraped_pages_site ON scraped_pages(site_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_scraped_pages_hash ON scraped_pages(content_hash)")

    conn.commit()
    conn.close()


def create_site(site_id: str, wp_base_url: str, wp_username: str, wp_app_password_enc: str, default_author_id: Optional[int] = None) -> None:
    """Create a new site record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sites (id, wp_base_url, wp_username, wp_app_password_enc, default_author_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (site_id, wp_base_url, wp_username, wp_app_password_enc, default_author_id, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_site(site_id: str) -> Optional[Dict[str, Any]]:
    """Get a site by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sites WHERE id = ?", (site_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def create_job(job_id: str, job_type: str, payload: Dict[str, Any]) -> None:
    """Create a new job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO jobs (id, type, status, payload_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (job_id, job_type, "queued", json.dumps(payload), now, now))
    conn.commit()
    conn.close()


def update_job(job_id: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[Dict[str, Any]] = None) -> None:
    """Update a job's status, result, and/or error."""
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["status = ?", "updated_at = ?"]
    values = [status, datetime.utcnow().isoformat()]

    if result is not None:
        updates.append("result_json = ?")
        values.append(json.dumps(result))

    if error is not None:
        updates.append("error_json = ?")
        values.append(json.dumps(error))

    values.append(job_id)
    cursor.execute(
        f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if row:
        job = dict(row)
        if job.get("payload_json"):
            job["payload"] = json.loads(job["payload_json"])
        if job.get("result_json"):
            job["result"] = json.loads(job["result_json"])
        if job.get("error_json"):
            job["error"] = json.loads(job["error_json"])
        conn.close()
        return job
    conn.close()
    return None


def get_queued_jobs() -> List[Dict[str, Any]]:
    """Get all queued jobs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_job_step(job_id: str, step: str, status: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """Add a step to a job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO job_steps (job_id, step, status, detail_json, ts)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, step, status, json.dumps(detail) if detail else None, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_job_steps(job_id: str) -> List[Dict[str, Any]]:
    """Get all steps for a job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM job_steps WHERE job_id = ? ORDER BY ts ASC", (job_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_scraped_pages(site_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get scraped pages for a site."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, url, title, page_type, fetched_at
        FROM scraped_pages
        WHERE site_id = ?
        ORDER BY fetched_at DESC
        LIMIT ?
    """, (site_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_page_chunks_count(site_id: str) -> int:
    """Get count of chunks for a site."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM page_chunks
        WHERE site_id = ?
    """, (site_id,))
    row = cursor.fetchone()
    conn.close()
    return row["count"] if row else 0
