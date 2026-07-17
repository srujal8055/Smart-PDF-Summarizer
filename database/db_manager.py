import os
import sqlite3
from typing import Optional

# Determine the absolute directory where this db_manager.py is located
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "summaries.db")

def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns an SQLite database connection."""
    # Ensure the database directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Enable dict factory to easily fetch rows as dictionaries
    conn.row_factory = sqlite3.Row
    return conn

def init_database() -> None:
    """Initializes the database schema by creating the summaries table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create summaries history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER NOT NULL,
            summary_type TEXT NOT NULL,
            final_summary TEXT NOT NULL,
            intermediate_summaries TEXT NOT NULL,  -- JSON serialized list
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print(f"Initializing database at: {DB_PATH}")
    init_database()
    print("Database initialization completed successfully.")
