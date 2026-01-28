import db

try:
    print("Testing database connection...")
    conn = db.get_db_connection()
    print("✅ Database connection OK")
    conn.close()

    print("\nTesting get_user_stats(1)...")
    stats = db.get_user_stats(1)
    print(f"✅ Stats: {stats}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
