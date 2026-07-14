import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = "test_projects/github_benchmarks/crawler_queue.db"

def setup_db(db_path=None):
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            repo TEXT NOT NULL,
            stars INTEGER,
            tag1 TEXT,
            tag2 TEXT,
            status TEXT DEFAULT 'pending',
            error_msg TEXT,
            processed_at TEXT,
            UNIQUE(owner, repo)
        )
    """)
    conn.commit()
    conn.close()

def mark_status(repo_id, status, error_msg=None, db_path=None):
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE queue SET status = ?, error_msg = ?, processed_at = ? WHERE id = ?",
        (status, error_msg, datetime.now(timezone.utc).isoformat(), repo_id)
    )
    conn.commit()
    conn.close()
