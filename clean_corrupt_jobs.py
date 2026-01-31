"""Clean corrupt jobs from database."""
import db
import json


def clean_corrupt_jobs():
    """Remove jobs with invalid JSON payload."""
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get all jobs
        cursor.execute("SELECT id, payload_json FROM jobs")
        jobs = cursor.fetchall()

        corrupt_ids = []
        for job in jobs:
            try:
                json.loads(job['payload_json'])
            except json.JSONDecodeError:
                corrupt_ids.append(job['id'])
                print(f"Found corrupt job: {job['id']}")

        if corrupt_ids:
            # Delete corrupt jobs
            placeholders = ','.join(['%s'] * len(corrupt_ids))
            cursor.execute(
                f"DELETE FROM jobs WHERE id IN ({placeholders})", corrupt_ids)
            conn.commit()
            print(f"✓ Deleted {len(corrupt_ids)} corrupt jobs")
        else:
            print("✓ No corrupt jobs found")

    except Exception as e:
        print(f"✗ Error cleaning jobs: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    clean_corrupt_jobs()
