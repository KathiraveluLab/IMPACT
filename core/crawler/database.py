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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transition_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            transitioned_at TEXT NOT NULL,
            error_msg TEXT,
            FOREIGN KEY(repo_id) REFERENCES queue(id)
        )
    """)
    conn.commit()
    conn.close()

def mark_status(repo_id, status, error_msg=None, db_path=None):
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Get current status
    cursor.execute("SELECT status FROM queue WHERE id = ?", (repo_id,))
    row = cursor.fetchone()
    from_status = row[0] if row else None
    
    now_str = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "UPDATE queue SET status = ?, error_msg = ?, processed_at = ? WHERE id = ?",
        (status, error_msg, now_str, repo_id)
    )
    
    cursor.execute(
        "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, error_msg) VALUES (?, ?, ?, ?, ?)",
        (repo_id, from_status, status, now_str, error_msg)
    )
    
    conn.commit()
    conn.close()
