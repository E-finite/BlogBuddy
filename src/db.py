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

    # Context Sites table - For scraped websites (not WordPress sites)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS context_sites (
            id VARCHAR(36) PRIMARY KEY,
            user_id INT NOT NULL,
            base_url VARCHAR(255) NOT NULL,
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

    # Scraped pages table - can reference both sites and context_sites
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_pages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(36) NOT NULL,
            site_type ENUM('wp', 'context') DEFAULT 'wp',
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
            UNIQUE KEY unique_site_url (site_id, url(191)),
            INDEX idx_site_id (site_id),
            INDEX idx_site_type (site_type),
            INDEX idx_content_hash (content_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # Add site_type column if it doesn't exist (migration)
    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = %s
            AND table_name = 'scraped_pages'
            AND column_name = 'site_type'
        """, (config.MYSQL_DATABASE,))
        
        result = cursor.fetchone()
        if result[0] == 0:
            cursor.execute("ALTER TABLE scraped_pages ADD COLUMN site_type ENUM('wp', 'context') DEFAULT 'wp' AFTER site_id")
            print("✅ Added site_type column to scraped_pages table")
    except Exception as e:
        print(f"⚠️ Migration note (scraped_pages): {e}")

    # Page chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_chunks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            page_id INT NOT NULL,
            site_id VARCHAR(36) NOT NULL,
            site_type ENUM('wp', 'context') DEFAULT 'wp',
            chunk_index INT NOT NULL,
            section_heading VARCHAR(255),
            chunk_text TEXT NOT NULL,
            chunk_tokens INT,
            url VARCHAR(500),
            FOREIGN KEY (page_id) REFERENCES scraped_pages(id) ON DELETE CASCADE,
            INDEX idx_site_id (site_id),
            INDEX idx_site_type (site_type),
            INDEX idx_page_id (page_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # Add site_type column if it doesn't exist (migration)
    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = %s
            AND table_name = 'page_chunks'
            AND column_name = 'site_type'
        """, (config.MYSQL_DATABASE,))
        
        result = cursor.fetchone()
        if result[0] == 0:
            cursor.execute("ALTER TABLE page_chunks ADD COLUMN site_type ENUM('wp', 'context') DEFAULT 'wp' AFTER site_id")
            print("✅ Added site_type column to page_chunks table")
    except Exception as e:
        print(f"⚠️ Migration note (page_chunks): {e}")

    # Site DNA table (brand identity extracted from website)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_dna (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(36) NOT NULL,
            site_type ENUM('wp', 'context') DEFAULT 'wp',
            brand_name VARCHAR(255),
            brand_colors_json TEXT,
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
            INDEX idx_site_id (site_id),
            INDEX idx_site_type (site_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # Add brand_name and brand_colors_json columns if they don't exist (migration)
    try:
        # First check and add site_type if needed
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = %s
            AND table_name = 'site_dna'
            AND column_name = 'site_type'
        """, (config.MYSQL_DATABASE,))
        
        has_site_type = cursor.fetchone()[0] > 0
        
        if not has_site_type:
            cursor.execute("ALTER TABLE site_dna ADD COLUMN site_type ENUM('wp', 'context') DEFAULT 'wp' AFTER site_id")
            print("✅ Added site_type column to site_dna table")
        
        # Then check and add brand_name
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = %s
            AND table_name = 'site_dna'
            AND column_name = 'brand_name'
        """, (config.MYSQL_DATABASE,))
        
        result = cursor.fetchone()
        if result[0] == 0:
            cursor.execute("ALTER TABLE site_dna ADD COLUMN brand_name VARCHAR(255) AFTER site_type")
            cursor.execute("ALTER TABLE site_dna ADD COLUMN brand_colors_json TEXT AFTER brand_name")
            print("✅ Added brand_name and brand_colors_json columns to site_dna table")
    except Exception as e:
        print(f"⚠️ Migration note (site_dna): {e}")

    # Drop foreign key constraint from scraped_pages to support both sites and context_sites
    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
            WHERE table_schema = %s
            AND table_name = 'scraped_pages'
            AND constraint_name = 'scraped_pages_ibfk_1'
        """, (config.MYSQL_DATABASE,))
        
        result = cursor.fetchone()
        if result[0] > 0:
            cursor.execute("ALTER TABLE scraped_pages DROP FOREIGN KEY scraped_pages_ibfk_1")
            print("✅ Dropped foreign key constraint scraped_pages_ibfk_1 to support context_sites")
    except Exception as e:
        print(f"⚠️ Migration note (scraped_pages FK): {e}")

    # Drop foreign key constraint from page_chunks to support both sites and context_sites
    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
            WHERE table_schema = %s
            AND table_name = 'page_chunks'
            AND constraint_name = 'page_chunks_ibfk_2'
        """, (config.MYSQL_DATABASE,))
        
        result = cursor.fetchone()
        if result[0] > 0:
            cursor.execute("ALTER TABLE page_chunks DROP FOREIGN KEY page_chunks_ibfk_2")
            print("✅ Dropped foreign key constraint page_chunks_ibfk_2 to support context_sites")
    except Exception as e:
        print(f"⚠️ Migration note (page_chunks FK): {e}")

    # Drop foreign key constraint from site_dna to support both sites and context_sites
    try:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
            WHERE table_schema = %s
            AND table_name = 'site_dna'
            AND constraint_name = 'site_dna_ibfk_1'
        """, (config.MYSQL_DATABASE,))
        
        result = cursor.fetchone()
        if result[0] > 0:
            cursor.execute("ALTER TABLE site_dna DROP FOREIGN KEY site_dna_ibfk_1")
            print("✅ Dropped foreign key constraint site_dna_ibfk_1 to support context_sites")
    except Exception as e:
        print(f"⚠️ Migration note (site_dna FK): {e}")

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


def delete_site(site_id: str, user_id: int) -> bool:
    """Delete a site and all its related data for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if site belongs to user
        cursor.execute(
            "SELECT id FROM sites WHERE id = %s AND user_id = %s", (site_id, user_id))
        if not cursor.fetchone():
            return False

        # Delete site (CASCADE will handle related data: scraped_pages, page_chunks, site_dna)
        cursor.execute(
            "DELETE FROM sites WHERE id = %s AND user_id = %s", (site_id, user_id))
        conn.commit()
        return True
    finally:
        cursor.close()
        conn.close()


def delete_user_sites(user_id: int) -> int:
    """Delete all WordPress sites for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM sites WHERE user_id = %s
        """, (user_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()


# Context Sites functions
def create_context_site(site_id: str, user_id: int, base_url: str) -> None:
    """Create a new context site record for scraped websites."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO context_sites (id, user_id, base_url, created_at)
        VALUES (%s, %s, %s, %s)
    """, (site_id, user_id, base_url, datetime.utcnow()))
    conn.commit()
    cursor.close()
    conn.close()


def get_context_site(site_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Get a context site by ID, optionally filtered by user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if user_id:
        cursor.execute(
            "SELECT * FROM context_sites WHERE id = %s AND user_id = %s", (site_id, user_id))
    else:
        cursor.execute("SELECT * FROM context_sites WHERE id = %s", (site_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_user_context_sites(user_id: int) -> List[Dict[str, Any]]:
    """Get all context sites for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM context_sites WHERE user_id = %s ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def cleanup_old_context_sites(user_id: int, days_old: int = 7) -> int:
    """Delete context sites older than specified days for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First, delete related data (scraped_pages, page_chunks, site_dna)
        cursor.execute("""
            DELETE sp, pc, sd FROM context_sites cs
            LEFT JOIN scraped_pages sp ON sp.site_id = cs.id AND sp.site_type = 'context'
            LEFT JOIN page_chunks pc ON pc.site_id = cs.id AND pc.site_type = 'context'
            LEFT JOIN site_dna sd ON sd.site_id = cs.id AND sd.site_type = 'context'
            WHERE cs.user_id = %s 
            AND cs.created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (user_id, days_old))
        
        # Then delete the context sites themselves
        cursor.execute("""
            DELETE FROM context_sites 
            WHERE user_id = %s 
            AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (user_id, days_old))
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()


def delete_all_context_sites(user_id: int) -> int:
    """Delete all context sites for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete related data first
        cursor.execute("""
            DELETE sp, pc, sd FROM context_sites cs
            LEFT JOIN scraped_pages sp ON sp.site_id = cs.id AND sp.site_type = 'context'
            LEFT JOIN page_chunks pc ON pc.site_id = cs.id AND pc.site_type = 'context'
            LEFT JOIN site_dna sd ON sd.site_id = cs.id AND sd.site_type = 'context'
            WHERE cs.user_id = %s
        """, (user_id,))
        
        # Then delete context sites
        cursor.execute("""
            DELETE FROM context_sites WHERE user_id = %s
        """, (user_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()


def delete_context_site(site_id: str, user_id: int) -> bool:
    """Delete a specific context site and its related data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if site belongs to user
        cursor.execute(
            "SELECT id FROM context_sites WHERE id = %s AND user_id = %s", (site_id, user_id))
        if not cursor.fetchone():
            return False
        
        # Delete related data
        cursor.execute("DELETE FROM scraped_pages WHERE site_id = %s AND site_type = 'context'", (site_id,))
        cursor.execute("DELETE FROM page_chunks WHERE site_id = %s AND site_type = 'context'", (site_id,))
        cursor.execute("DELETE FROM site_dna WHERE site_id = %s AND site_type = 'context'", (site_id,))
        
        # Delete context site
        cursor.execute(
            "DELETE FROM context_sites WHERE id = %s AND user_id = %s", (site_id, user_id))
        conn.commit()
        return True
    finally:
        cursor.close()
        conn.close()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM sites 
            WHERE user_id = %s AND wp_username = '__context_temp__'
        """, (user_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()


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
