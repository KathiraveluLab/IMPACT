import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = "test_projects/github_benchmarks/crawler_queue.db"

def setup_db(db_path=None):
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    if path.startswith("postgresql://") or path.startswith("postgres://"):
        import psycopg2
        conn = psycopg2.connect(path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id SERIAL PRIMARY KEY,
                owner VARCHAR(255) NOT NULL,
                repo VARCHAR(255) NOT NULL,
                stars INTEGER,
                tag1 VARCHAR(100),
                tag2 VARCHAR(100),
                status VARCHAR(50) DEFAULT 'pending',
                error_msg TEXT,
                processed_at VARCHAR(100),
                UNIQUE(owner, repo)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transition_history (
                id SERIAL PRIMARY KEY,
                repo_id INTEGER NOT NULL REFERENCES queue(id),
                from_status VARCHAR(50),
                to_status VARCHAR(50) NOT NULL,
                transitioned_at VARCHAR(100) NOT NULL,
                error_msg TEXT
            )
        """)
        conn.commit()
        conn.close()
    else:
        if os.path.dirname(path):
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
    now_str = datetime.now(timezone.utc).isoformat()
    if path.startswith("postgresql://") or path.startswith("postgres://"):
        import psycopg2
        conn = psycopg2.connect(path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT status FROM queue WHERE id = %s", (repo_id,))
            row = cursor.fetchone()
            from_status = row[0] if row else None
            
            cursor.execute(
                "UPDATE queue SET status = %s, error_msg = %s, processed_at = %s WHERE id = %s",
                (status, error_msg, now_str, repo_id)
            )
            cursor.execute(
                "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, error_msg) VALUES (%s, %s, %s, %s, %s)",
                (repo_id, from_status, status, now_str, error_msg)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM queue WHERE id = ?", (repo_id,))
        row = cursor.fetchone()
        from_status = row[0] if row else None
        
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

def claim_next_pending(db_path=None):
    """Atomically claims the next pending repository for processing using database-level locking."""
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    now_str = datetime.now(timezone.utc).isoformat()
    
    if path.startswith("postgresql://") or path.startswith("postgres://"):
        import psycopg2
        conn = psycopg2.connect(path)
        cursor = conn.cursor()
        try:
            # Atomic row claim using SELECT FOR UPDATE SKIP LOCKED
            cursor.execute("""
                SELECT id, owner, repo FROM queue 
                WHERE status = 'pending' 
                ORDER BY stars DESC 
                LIMIT 1 
                FOR UPDATE SKIP LOCKED
            """)
            row = cursor.fetchone()
            if row:
                repo_id, owner, repo = row
                cursor.execute(
                    "UPDATE queue SET status = 'processing', processed_at = %s WHERE id = %s",
                    (now_str, repo_id)
                )
                cursor.execute(
                    "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at) VALUES (%s, %s, %s, %s)",
                    (repo_id, 'pending', 'processing', now_str)
                )
                conn.commit()
                return repo_id, owner, repo
            return None
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor.execute("""
                SELECT id, owner, repo FROM queue 
                WHERE status = 'pending' 
                ORDER BY stars DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                repo_id, owner, repo = row
                cursor.execute(
                    "UPDATE queue SET status = 'processing', processed_at = ? WHERE id = ?",
                    (now_str, repo_id)
                )
                cursor.execute(
                    "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at) VALUES (?, ?, ?, ?)",
                    (repo_id, 'pending', 'processing', now_str)
                )
                conn.commit()
                return repo_id, owner, repo
            conn.commit()
            return None
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
