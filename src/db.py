"""Database initialization and utilities."""
import mysql.connector
from mysql.connector import Error
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from src import config


def get_db_connection():
    """Get a MySQL database connection."""
    try:
        conn = mysql.connector.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE
        )
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise


def init_db():
    """Initialize the database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table for authentication (create first for foreign keys)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL,
            last_login DATETIME NULL,
            is_active TINYINT(1) DEFAULT 1,
            INDEX idx_username (username),
            INDEX idx_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Sites table - MULTI-TENANT: each site belongs to a user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id VARCHAR(36) PRIMARY KEY,
            user_id INT NOT NULL,
            wp_base_url VARCHAR(255) NOT NULL,
            wp_username VARCHAR(100) NOT NULL,
            wp_app_password_enc TEXT NOT NULL,
            default_author_id INTEGER NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Jobs table - MULTI-TENANT: each job belongs to a user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id VARCHAR(36) PRIMARY KEY,
            user_id INT NOT NULL,
            type VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            payload_json LONGTEXT NOT NULL,
            result_json LONGTEXT,
            error_json TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_status (status),
            INDEX idx_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Job steps table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_steps (
            id INT AUTO_INCREMENT PRIMARY KEY,
            job_id VARCHAR(36) NOT NULL,
            step VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL,
            detail_json TEXT,
            ts DATETIME NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            INDEX idx_job_id (job_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Scraped pages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_pages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(36) NOT NULL,
            url VARCHAR(500) NOT NULL,
            canonical_url VARCHAR(500),
            title VARCHAR(255),
            clean_text LONGTEXT,
            headings_json TEXT,
            html_snippet TEXT,
            status_code INT,
            fetched_at DATETIME NOT NULL,
            content_hash VARCHAR(64),
            page_type VARCHAR(50),
            FOREIGN KEY (site_id) REFERENCES sites(id),
            UNIQUE KEY unique_site_url (site_id, url(191)),
            INDEX idx_site_id (site_id),
            INDEX idx_content_hash (content_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Page chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_chunks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            page_id INT NOT NULL,
            site_id VARCHAR(36) NOT NULL,
            chunk_index INT NOT NULL,
            section_heading VARCHAR(255),
            chunk_text TEXT NOT NULL,
            chunk_tokens INT,
            url VARCHAR(500),
            FOREIGN KEY (page_id) REFERENCES scraped_pages(id),
            FOREIGN KEY (site_id) REFERENCES sites(id),
            INDEX idx_site_id (site_id),
            INDEX idx_page_id (page_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Site DNA table (brand identity extracted from website)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_dna (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(36) NOT NULL,
            brand_summary TEXT,
            target_audiences_json TEXT,
            pain_points_json TEXT,
            solutions_themes_json TEXT,
            tone_keywords_json TEXT,
            avoid_words_json TEXT,
            proof_points_json TEXT,
            compliance_notes_json TEXT,
            generated_at DATETIME NOT NULL,
            source_pages_json TEXT,
            FOREIGN KEY (site_id) REFERENCES sites(id),
            INDEX idx_site_id (site_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    conn.commit()
    cursor.close()
    conn.close()


def create_site(site_id: str, user_id: int, wp_base_url: str, wp_username: str, wp_app_password_enc: str, default_author_id: Optional[int] = None) -> None:
    """Create a new site record for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sites (id, user_id, wp_base_url, wp_username, wp_app_password_enc, default_author_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (site_id, user_id, wp_base_url, wp_username, wp_app_password_enc, default_author_id, datetime.utcnow()))
    conn.commit()
    cursor.close()
    conn.close()


def get_site(site_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Get a site by ID, optionally filtered by user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if user_id:
        cursor.execute(
            "SELECT * FROM sites WHERE id = %s AND user_id = %s", (site_id, user_id))
    else:
        cursor.execute("SELECT * FROM sites WHERE id = %s", (site_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def create_job(job_id: str, user_id: int, job_type: str, payload: Dict[str, Any]) -> None:
    """Create a new job for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow()
    cursor.execute("""
        INSERT INTO jobs (id, user_id, type, status, payload_json, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (job_id, user_id, job_type, "queued", json.dumps(payload), now, now))
    conn.commit()
    cursor.close()
    conn.close()


def update_job(job_id: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[Dict[str, Any]] = None) -> None:
    """Update a job's status, result, and/or error."""
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = ["status = %s", "updated_at = %s"]
    values = [status, datetime.utcnow()]

    if result is not None:
        updates.append("result_json = %s")
        values.append(json.dumps(result))

    if error is not None:
        updates.append("error_json = %s")
        values.append(json.dumps(error))

    values.append(job_id)
    cursor.execute(
        f"UPDATE jobs SET {', '.join(updates)} WHERE id = %s", values)
    conn.commit()
    cursor.close()
    conn.close()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
    row = cursor.fetchone()
    if row:
        job = dict(row)
        if job.get("payload_json"):
            job["payload"] = json.loads(job["payload_json"])
        if job.get("result_json"):
            job["result"] = json.loads(job["result_json"])
        if job.get("error_json"):
            job["error"] = json.loads(job["error_json"])
        cursor.close()
        conn.close()
        return job
    cursor.close()
    conn.close()
    return None


def get_queued_jobs() -> List[Dict[str, Any]]:
    """Get all queued jobs."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def add_job_step(job_id: str, step: str, status: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """Add a step to a job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO job_steps (job_id, step, status, detail_json, ts)
        VALUES (%s, %s, %s, %s, %s)
    """, (job_id, step, status, json.dumps(detail) if detail else None, datetime.utcnow()))
    conn.commit()
    cursor.close()
    conn.close()


def get_job_steps(job_id: str) -> List[Dict[str, Any]]:
    """Get all steps for a job."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM job_steps WHERE job_id = %s ORDER BY ts ASC", (job_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_scraped_pages(site_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get scraped pages for a site."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, url, title, page_type, fetched_at
        FROM scraped_pages
        WHERE site_id = %s
        ORDER BY fetched_at DESC
        LIMIT %s
    """, (site_id, limit))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_page_chunks_count(site_id: str) -> int:
    """Get count of chunks for a site."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM page_chunks
        WHERE site_id = %s
    """, (site_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else 0


# User management functions
def create_user(username: str, email: str, password_hash: str) -> int:
    """Create a new user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, created_at)
        VALUES (%s, %s, %s, %s)
    """, (username, email, password_hash, datetime.utcnow()))
    user_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return user_id


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get a user by email."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get a user by ID."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def update_user_last_login(user_id: int) -> None:
    """Update user's last login timestamp."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET last_login = %s WHERE id = %s
    """, (datetime.utcnow(), user_id))
    conn.commit()
    cursor.close()
    conn.close()


# Multi-tenant helper functions
def get_user_sites(user_id: int) -> List[Dict[str, Any]]:
    """Get all sites for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM sites WHERE user_id = %s ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_user_jobs(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent jobs for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM jobs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s
    """, (user_id, limit))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_user_stats(user_id: int) -> Dict[str, int]:
    """Get statistics for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Count sites
    cursor.execute(
        "SELECT COUNT(*) as count FROM sites WHERE user_id = %s", (user_id,))
    sites_count = cursor.fetchone()['count']

    # Count jobs
    cursor.execute(
        "SELECT COUNT(*) as count FROM jobs WHERE user_id = %s", (user_id,))
    jobs_count = cursor.fetchone()['count']

    # Count completed jobs
    cursor.execute(
        "SELECT COUNT(*) as count FROM jobs WHERE user_id = %s AND status = 'completed'", (user_id,))
    completed_jobs = cursor.fetchone()['count']

    cursor.close()
    conn.close()

    return {
        'sites': sites_count,
        'jobs': jobs_count,
        'completed_jobs': completed_jobs
    }
