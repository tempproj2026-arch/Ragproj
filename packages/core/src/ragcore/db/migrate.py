from pathlib import Path
from .connection import Database

def run_migrations():
    migrations_dir = Path(__file__).parent / "migrations"
    migration_file = migrations_dir / "001_init.sql"
    
    print(f"Running migration: {migration_file.name}")
    with Database.get_connection() as conn:
        with conn.cursor() as cur:
            sql = migration_file.read_text(encoding="utf-8")
            cur.execute(sql)
            conn.commit()
    print("Migrations completed successfully.")

if __name__ == "__main__":
    run_migrations()
