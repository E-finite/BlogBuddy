import db
import mysql.connector
import config

# Connect to database
conn = mysql.connector.connect(
    host=config.MYSQL_HOST,
    port=config.MYSQL_PORT,
    user=config.MYSQL_USER,
    password=config.MYSQL_PASSWORD,
    database=config.MYSQL_DATABASE
)

cursor = conn.cursor()

# Disable foreign key checks
cursor.execute('SET FOREIGN_KEY_CHECKS = 0')

# Drop all tables
tables = ['job_steps', 'page_chunks', 'scraped_pages',
          'site_dna', 'jobs', 'sites', 'users']
for table in tables:
    cursor.execute(f'DROP TABLE IF EXISTS {table}')
    print(f'Dropped table: {table}')

# Re-enable foreign key checks
cursor.execute('SET FOREIGN_KEY_CHECKS = 1')

conn.commit()
cursor.close()
conn.close()

print('\n✅ Alle tabellen verwijderd! Nu init_db() runnen...')

# Recreate tables
db.init_db()
print('✅ Multi-tenant database aangemaakt!')
