import os
import psycopg2
from pathlib import Path

# Connect to database
conn = psycopg2.connect(
    dbname="postgres",
    user="postgres.your-tenant-id",
    password="your-super-secret-and-long-postgres-password",
    host="127.0.0.1",
    port=5432
)
conn.autocommit = True
cursor = conn.cursor()

# Run migrations
migrations_dir = Path("supabase/migrations")
migrations = sorted([f for f in migrations_dir.iterdir() if f.name.endswith(".sql")])

for migration in migrations:
    print(f"Running {migration.name}...")
    with open(migration, "r", encoding="utf-8") as f:
        sql = f.read()
        try:
            cursor.execute(sql)
            print(f"✅ Success: {migration.name}")
        except Exception as e:
            print(f"❌ Error in {migration.name}: {e}")

# Create storage buckets
print("Creating storage buckets...")
try:
    cursor.execute("""
    INSERT INTO storage.buckets (id, name, public) 
    VALUES ('books', 'books', false), ('covers', 'covers', true)
    ON CONFLICT (id) DO NOTHING;
    """)
    print("✅ Success: Created storage buckets")
except Exception as e:
    print(f"❌ Error creating buckets: {e}")

cursor.close()
conn.close()
print("Done!")
