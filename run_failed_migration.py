
import psycopg2
from pathlib import Path
conn = psycopg2.connect(dbname="postgres", user="postgres.your-tenant-id", password="your-super-secret-and-long-postgres-password", host="127.0.0.1", port=5432)
conn.autocommit = True
cursor = conn.cursor()
with open("supabase/migrations/002_performance_indexes.sql", "r") as f:
    cursor.execute(f.read())
print("✅ Success: 002_performance_indexes.sql")

