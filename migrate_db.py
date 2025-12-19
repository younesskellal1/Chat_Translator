"""Database migration script to add missing columns to users table."""
from sqlalchemy import create_engine, text
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=True)

def migrate_db():
    """Add missing columns to users table."""
    with ENGINE.connect() as conn:
        # Check if columns exist
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]

        if 'default_source' not in columns:
            print("Adding default_source column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN default_source VARCHAR(40)"))
            conn.commit()

        if 'default_target' not in columns:
            print("Adding default_target column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN default_target VARCHAR(40)"))
            conn.commit()

        print("Migration completed.")

if __name__ == "__main__":
    migrate_db()
