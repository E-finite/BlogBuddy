"""Database initialization and utilities."""
import mysql.connector
from mysql.connector import Error
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from src import config

logger = logging.getLogger(__name__)


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
            cursor.execute(
                "ALTER TABLE scraped_pages ADD COLUMN site_type ENUM('wp', 'context') DEFAULT 'wp' AFTER site_id")
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
            cursor.execute(
                "ALTER TABLE page_chunks ADD COLUMN site_type ENUM('wp', 'context') DEFAULT 'wp' AFTER site_id")
            print("✅ Added site_type column to page_chunks table")
    except Exception as e:
        print(f"⚠️ Migration note (page_chunks): {e}")

    # Site DNA table (brand identity extracted from website)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_dna (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_id VARCHAR(36) NOT NULL,
            user_id INT NULL,
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
            INDEX idx_user_id (user_id),
            INDEX idx_site_type (site_type),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # Migration: Add user_id column if it doesn't exist
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = %s
            AND table_name = 'site_dna'
            AND column_name = 'user_id'
        """, (config.MYSQL_DATABASE,))

        result = cursor.fetchone()
        if result[0] == 0:
            cursor.execute(
                "ALTER TABLE site_dna ADD COLUMN user_id INT NULL AFTER site_id, ADD INDEX idx_user_id (user_id), ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE")
            print("✅ Added user_id column to site_dna table")
    except Exception as e:
        print(f"⚠️ Migration note (site_dna): {e}")
    # Image generations table - stores generated images with regeneration chains
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_generations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            job_id VARCHAR(36) NULL,
            parent_id INT NULL,
            generation_number INT NOT NULL DEFAULT 1,
            
            topic VARCHAR(500) NOT NULL,
            brand_json TEXT,
            image_settings_json TEXT NOT NULL,
            
            user_feedback TEXT NULL,
            all_feedback_json TEXT NULL,
            
            prompt_used TEXT NOT NULL,
            image_data LONGBLOB NULL,
            mime_type VARCHAR(50),
            filename VARCHAR(255),
            
            wordpress_media_id INT NULL,
            uploaded_at DATETIME NULL,
            
            created_at DATETIME NOT NULL,
            status ENUM('generating', 'completed', 'failed') DEFAULT 'completed',
            error_message TEXT NULL,
            
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES image_generations(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_job_id (job_id),
            INDEX idx_parent_id (parent_id),
            INDEX idx_created (created_at),
            INDEX idx_wordpress_media_id (wordpress_media_id)
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
            cursor.execute(
                "ALTER TABLE site_dna ADD COLUMN site_type ENUM('wp', 'context') DEFAULT 'wp' AFTER site_id")
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
            cursor.execute(
                "ALTER TABLE site_dna ADD COLUMN brand_name VARCHAR(255) AFTER site_type")
            cursor.execute(
                "ALTER TABLE site_dna ADD COLUMN brand_colors_json TEXT AFTER brand_name")
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
            cursor.execute(
                "ALTER TABLE scraped_pages DROP FOREIGN KEY scraped_pages_ibfk_1")
            print(
                "✅ Dropped foreign key constraint scraped_pages_ibfk_1 to support context_sites")
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
            cursor.execute(
                "ALTER TABLE page_chunks DROP FOREIGN KEY page_chunks_ibfk_2")
            print(
                "✅ Dropped foreign key constraint page_chunks_ibfk_2 to support context_sites")
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
            cursor.execute(
                "ALTER TABLE site_dna DROP FOREIGN KEY site_dna_ibfk_1")
            print(
                "✅ Dropped foreign key constraint site_dna_ibfk_1 to support context_sites")
    except Exception as e:
        print(f"⚠️ Migration note (site_dna FK): {e}")

    # Drafts table - stores generated blog drafts that are ready to publish
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            site_id VARCHAR(36) NULL,
            draft_json LONGTEXT NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_site_id (site_id),
            INDEX idx_created (created_at)
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
        cursor.execute(
            "DELETE FROM scraped_pages WHERE site_id = %s AND site_type = 'context'", (site_id,))
        cursor.execute(
            "DELETE FROM page_chunks WHERE site_id = %s AND site_type = 'context'", (site_id,))
        cursor.execute(
            "DELETE FROM site_dna WHERE site_id = %s AND site_type = 'context'", (site_id,))

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


# Image generation functions
def save_image_generation(
    user_id: int,
    topic: str,
    image_settings: Dict[str, Any],
    prompt_used: str,
    image_data: bytes,
    mime_type: str,
    filename: str,
    brand: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    parent_id: Optional[int] = None,
    user_feedback: Optional[str] = None,
    all_feedback: Optional[List[str]] = None
) -> int:
    """
    Save a generated image to database.
    Returns the new image_generation id.
    """
    # ALWAYS compress images to ensure they fit in MySQL packet size
    # MySQL default max_allowed_packet is often 4MB, but can be as low as 1MB
    # We target 1MB to be safe across all MySQL configurations
    TARGET_SIZE = 1 * 1024 * 1024  # 1MB target
    MAX_SIZE = 1.5 * 1024 * 1024   # 1.5MB hard limit
    
    original_size = len(image_data)
    logger.info(f"Original image size: {original_size} bytes ({original_size/1024/1024:.2f}MB)")
    
    # ALWAYS compress/optimize images, even if under limit
    try:
        from PIL import Image
        import io
        
        # Load image
        img = Image.open(io.BytesIO(image_data))
        original_format = img.format
        original_size_tuple = img.size
        
        # Determine target dimensions based on current size
        max_width = 1600  # Good balance between quality and file size
        max_height = 1200
        
        # Resize if needed
        if img.size[0] > max_width or img.size[1] > max_height:
            logger.info(f"Resizing image from {img.size}")
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            logger.info(f"Resized to {img.size}")
        
        # Start with quality 85 and reduce until we hit target
        quality = 85
        compressed_data = None
        
        while quality >= 30:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            compressed_data = buffer.getvalue()
            size_mb = len(compressed_data) / 1024 / 1024
            
            logger.info(f"Quality {quality}: {len(compressed_data)} bytes ({size_mb:.2f}MB)")
            
            if len(compressed_data) <= TARGET_SIZE:
                break
            
            quality -= 5
        
        # If still too large after minimum quality, resize more aggressively
        if len(compressed_data) > MAX_SIZE:
            logger.warning(f"Still too large ({len(compressed_data)} bytes), aggressive resize")
            img.thumbnail((1200, 900), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=75, optimize=True)
            compressed_data = buffer.getvalue()
            
            # Final check - if STILL too large, go nuclear
            if len(compressed_data) > MAX_SIZE:
                logger.error("Extreme case: resizing to 800px")
                img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=70, optimize=True)
                compressed_data = buffer.getvalue()
        
        image_data = compressed_data
        mime_type = 'image/jpeg'
        final_size_mb = len(image_data) / 1024 / 1024
        compression_ratio = (1 - len(image_data) / original_size) * 100
        logger.info(f"✅ Final image: {len(image_data)} bytes ({final_size_mb:.2f}MB), {compression_ratio:.1f}% compression")
        
    except Exception as e:
        logger.error(f"Failed to compress image: {e}", exc_info=True)
        # Last resort: truncate (will corrupt image but prevents crash)
        logger.error("CRITICAL: Truncating image as last resort")
        image_data = image_data[:TARGET_SIZE]
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Determine generation number
    generation_number = 1
    if parent_id:
        cursor.execute(
            "SELECT generation_number FROM image_generations WHERE id = %s",
            (parent_id,)
        )
        parent = cursor.fetchone()
        if parent:
            generation_number = parent[0] + 1

    cursor.execute("""
        INSERT INTO image_generations (
            user_id, job_id, parent_id, generation_number,
            topic, brand_json, image_settings_json,
            user_feedback, all_feedback_json,
            prompt_used, image_data, mime_type, filename,
            created_at, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        user_id, job_id, parent_id, generation_number,
        topic,
        json.dumps(brand) if brand else None,
        json.dumps(image_settings),
        user_feedback,
        json.dumps(all_feedback) if all_feedback else None,
        prompt_used, image_data, mime_type, filename,
        datetime.utcnow(), 'completed'
    ))

    image_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    return image_id


def get_image_generation(image_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get an image generation by ID.
    Validates that the image belongs to the user.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM image_generations 
        WHERE id = %s AND user_id = %s
    """, (image_id, user_id))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    return row


def get_feedback_chain(image_id: int, user_id: int) -> List[str]:
    """
    Get the complete feedback chain for an image by traversing parent relationships.
    Returns list of feedback strings in chronological order.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT all_feedback_json FROM image_generations 
        WHERE id = %s AND user_id = %s
    """, (image_id, user_id))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row and row['all_feedback_json']:
        return json.loads(row['all_feedback_json'])
    return []


def validate_regeneration_limit(image_id: int, user_id: int) -> tuple[bool, str]:
    """
    Validate if regeneration is allowed for this image.
    Returns (is_valid, error_message).
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT generation_number FROM image_generations 
        WHERE id = %s AND user_id = %s
    """, (image_id, user_id))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return False, "Image generation not found"

    if row['generation_number'] >= 3:
        return False, "Maximum regeneration limit (3 generations) reached"

    return True, ""


def update_image_uploaded(image_id: int, wordpress_media_id: int) -> None:
    """
    Mark an image as uploaded to WordPress with media ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE image_generations 
        SET wordpress_media_id = %s, uploaded_at = %s
        WHERE id = %s
    """, (wordpress_media_id, datetime.utcnow(), image_id))

    conn.commit()
    cursor.close()
    conn.close()


def cleanup_job_images(job_id: str) -> int:
    """
    Delete images for a job that have been successfully uploaded to WordPress.
    Returns count of deleted images.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM image_generations 
        WHERE job_id = %s AND wordpress_media_id IS NOT NULL
    """, (job_id,))

    deleted_count = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()

    return deleted_count


# ============================================
# DRAFTS
# ============================================

def create_draft(user_id: int, site_id: Optional[str], draft_data: dict) -> int:
    """
    Save a generated draft to the database.
    Returns the draft ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.utcnow()
    draft_json = json.dumps(draft_data)
    
    # Log size to help diagnose issues
    draft_size_mb = len(draft_json.encode('utf-8')) / 1024 / 1024
    logger.info(f"Draft JSON size: {draft_size_mb:.2f}MB")
    
    # Warn if draft is getting large (MySQL default max_allowed_packet is 4MB)
    if draft_size_mb > 3:
        logger.warning(f"Draft size ({draft_size_mb:.2f}MB) is very large. Consider removing large data.")
    
    cursor.execute("""
        INSERT INTO drafts (user_id, site_id, draft_json, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, site_id, draft_json, now, now))
    
    draft_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    
    return draft_id


def get_user_drafts(user_id: int) -> List[Dict[str, Any]]:
    """
    Get all drafts for a specific user.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT id, user_id, site_id, draft_json, created_at, updated_at
        FROM drafts
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Parse JSON data
    drafts = []
    for row in rows:
        draft = {
            'id': row['id'],
            'user_id': row['user_id'],
            'site_id': row['site_id'],
            'draft': json.loads(row['draft_json']) if row['draft_json'] else {},
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
        }
        drafts.append(draft)
    
    return drafts


def get_draft(draft_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific draft by ID, ensuring it belongs to the user.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT id, user_id, site_id, draft_json, created_at, updated_at
        FROM drafts
        WHERE id = %s AND user_id = %s
    """, (draft_id, user_id))
    
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not row:
        return None
    
    draft = {
        'id': row['id'],
        'user_id': row['user_id'],
        'site_id': row['site_id'],
        'draft': json.loads(row['draft_json']) if row['draft_json'] else {},
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
    }
    
    return draft


def delete_draft(draft_id: int, user_id: int) -> bool:
    """
    Delete a draft, ensuring it belongs to the user.
    Returns True if deleted, False if not found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM drafts
        WHERE id = %s AND user_id = %s
    """, (draft_id, user_id))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()
    
    return deleted
