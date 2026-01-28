"""
Cleanup script to remove context-only sites from the database.
These are sites that were created for crawling context, not real WordPress connections.
"""

import db


def cleanup_context_sites():
    """Remove all temporary context sites (username '__context_temp__')."""
    conn = db.get_db_connection()
    cursor = conn.cursor()

    # First, count them
    cursor.execute(
        "SELECT COUNT(*) FROM sites WHERE wp_username = '__context_temp__'")
    count = cursor.fetchone()[0]

    if count == 0:
        print("✅ No temporary context sites found. Database is clean!")
        cursor.close()
        conn.close()
        return

    print(f"Found {count} temporary context sites to remove...")

    # Delete them
    cursor.execute("DELETE FROM sites WHERE wp_username = '__context_temp__'")
    conn.commit()

    print(f"✅ Removed {count} temporary context sites from database!")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    cleanup_context_sites()
