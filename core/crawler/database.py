import sqlite3
import os
import socket
from datetime import datetime, timezone, timedelta

DB_PATH = "test_projects/github_benchmarks/crawler_queue.db"

# Default timeout: rows stuck in 'processing' longer than this are reclaimed.
STALE_TIMEOUT_MINUTES = 30


def _worker_id():
    """Unique identifier for the current worker process (hostname + PID)."""
    return f"{socket.gethostname()}:{os.getpid()}"


def _is_pg(path):
    return path.startswith("postgresql://") or path.startswith("postgres://")


def setup_db(db_path=None):
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    if _is_pg(path):
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
                worker_id VARCHAR(255),
                claimed_at VARCHAR(100),
                language VARCHAR(50) DEFAULT 'java',
                extraction_start_at VARCHAR(100),
                extraction_end_at VARCHAR(100),
                loc_v1 INTEGER,
                loc_v2 INTEGER,
                classes_v1 INTEGER,
                classes_v2 INTEGER,
                coupling_v1 DOUBLE PRECISION,
                coupling_v2 DOUBLE PRECISION,
                conforms_v1 BOOLEAN,
                conforms_v2 BOOLEAN,
                added_nodes INTEGER,
                removed_nodes INTEGER,
                added_edges INTEGER,
                removed_edges INTEGER,
                new_cycles INTEGER,
                broken_cycles INTEGER,
                intent_status VARCHAR(50),
                top_hubs TEXT,
                coupling_anomalies TEXT,
                report_content TEXT,
                graph_v1_path TEXT,
                graph_v2_path TEXT,
                report_path TEXT,
                UNIQUE(owner, repo)
            )
        """)
        # Migrate existing databases that lack the new columns
        for col, typedef in [
            ("worker_id", "VARCHAR(255)"),
            ("claimed_at", "VARCHAR(100)"),
            ("language", "VARCHAR(50) DEFAULT 'java'"),
            ("extraction_start_at", "VARCHAR(100)"),
            ("extraction_end_at", "VARCHAR(100)"),
            ("loc_v1", "INTEGER"),
            ("loc_v2", "INTEGER"),
            ("classes_v1", "INTEGER"),
            ("classes_v2", "INTEGER"),
            ("coupling_v1", "DOUBLE PRECISION"),
            ("coupling_v2", "DOUBLE PRECISION"),
            ("conforms_v1", "BOOLEAN"),
            ("conforms_v2", "BOOLEAN"),
            ("added_nodes", "INTEGER"),
            ("removed_nodes", "INTEGER"),
            ("added_edges", "INTEGER"),
            ("removed_edges", "INTEGER"),
            ("new_cycles", "INTEGER"),
            ("broken_cycles", "INTEGER"),
            ("intent_status", "VARCHAR(50)"),
            ("top_hubs", "TEXT"),
            ("coupling_anomalies", "TEXT"),
            ("report_content", "TEXT"),
            ("graph_v1_path", "TEXT"),
            ("graph_v2_path", "TEXT"),
            ("report_path", "TEXT")
        ]:
            cursor.execute(f"""
                ALTER TABLE queue ADD COLUMN IF NOT EXISTS {col} {typedef}
            """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transition_history (
                id SERIAL PRIMARY KEY,
                repo_id INTEGER NOT NULL REFERENCES queue(id),
                from_status VARCHAR(50),
                to_status VARCHAR(50) NOT NULL,
                transitioned_at VARCHAR(100) NOT NULL,
                error_msg TEXT,
                worker_id VARCHAR(255)
            )
        """)
        cursor.execute("""
            ALTER TABLE transition_history
            ADD COLUMN IF NOT EXISTS worker_id VARCHAR(255)
        """)
        conn.commit()
        conn.close()
    else:
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
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
                worker_id TEXT,
                claimed_at TEXT,
                language TEXT DEFAULT 'java',
                extraction_start_at TEXT,
                extraction_end_at TEXT,
                loc_v1 INTEGER,
                loc_v2 INTEGER,
                classes_v1 INTEGER,
                classes_v2 INTEGER,
                coupling_v1 REAL,
                coupling_v2 REAL,
                conforms_v1 INTEGER,
                conforms_v2 INTEGER,
                added_nodes INTEGER,
                removed_nodes INTEGER,
                added_edges INTEGER,
                removed_edges INTEGER,
                new_cycles INTEGER,
                broken_cycles INTEGER,
                intent_status TEXT,
                top_hubs TEXT,
                coupling_anomalies TEXT,
                report_content TEXT,
                graph_v1_path TEXT,
                graph_v2_path TEXT,
                report_path TEXT,
                UNIQUE(owner, repo)
            )
        """)
        # Migrate existing databases that lack the new columns
        existing = {row[1] for row in cursor.execute("PRAGMA table_info(queue)")}
        for col, typedef in [
            ("worker_id", "TEXT"),
            ("claimed_at", "TEXT"),
            ("language", "TEXT DEFAULT 'java'"),
            ("extraction_start_at", "TEXT"),
            ("extraction_end_at", "TEXT"),
            ("loc_v1", "INTEGER"),
            ("loc_v2", "INTEGER"),
            ("classes_v1", "INTEGER"),
            ("classes_v2", "INTEGER"),
            ("coupling_v1", "REAL"),
            ("coupling_v2", "REAL"),
            ("conforms_v1", "INTEGER"),
            ("conforms_v2", "INTEGER"),
            ("added_nodes", "INTEGER"),
            ("removed_nodes", "INTEGER"),
            ("added_edges", "INTEGER"),
            ("removed_edges", "INTEGER"),
            ("new_cycles", "INTEGER"),
            ("broken_cycles", "INTEGER"),
            ("intent_status", "TEXT"),
            ("top_hubs", "TEXT"),
            ("coupling_anomalies", "TEXT"),
            ("report_content", "TEXT"),
            ("graph_v1_path", "TEXT"),
            ("graph_v2_path", "TEXT"),
            ("report_path", "TEXT")
        ]:
            if col not in existing:
                cursor.execute(f"ALTER TABLE queue ADD COLUMN {col} {typedef}")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transition_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                transitioned_at TEXT NOT NULL,
                error_msg TEXT,
                worker_id TEXT,
                FOREIGN KEY(repo_id) REFERENCES queue(id)
            )
        """)
        existing_h = {row[1] for row in cursor.execute("PRAGMA table_info(transition_history)")}
        if "worker_id" not in existing_h:
            cursor.execute("ALTER TABLE transition_history ADD COLUMN worker_id TEXT")
        conn.commit()
        conn.close()


def mark_status(repo_id, status, error_msg=None, db_path=None):
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    now_str = datetime.now(timezone.utc).isoformat()
    wid = _worker_id()
    if _is_pg(path):
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
                "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, error_msg, worker_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (repo_id, from_status, status, now_str, error_msg, wid)
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
            "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, error_msg, worker_id) VALUES (?, ?, ?, ?, ?, ?)",
            (repo_id, from_status, status, now_str, error_msg, wid)
        )
        conn.commit()
        conn.close()


def claim_next_pending(db_path=None, stale_timeout_minutes=STALE_TIMEOUT_MINUTES):
    """Atomically claims the next pending (or stale processing) repository.

    A row stuck in 'processing' longer than *stale_timeout_minutes* is
    automatically reclaimed, covering crashed or hung worker processes.
    """
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    now_str = datetime.now(timezone.utc).isoformat()
    stale_cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=stale_timeout_minutes)
    ).isoformat()
    wid = _worker_id()

    if _is_pg(path):
        import psycopg2
        conn = psycopg2.connect(path)
        cursor = conn.cursor()
        try:
            # Claim pending OR stale processing rows (crashed workers)
            cursor.execute("""
                SELECT id, owner, repo FROM queue
                WHERE status = 'pending'
                   OR (status = 'processing' AND claimed_at < %s)
                ORDER BY stars DESC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """, (stale_cutoff,))
            row = cursor.fetchone()
            if row:
                repo_id, owner, repo = row
                cursor.execute(
                    "UPDATE queue SET status = 'processing', claimed_at = %s, worker_id = %s WHERE id = %s",
                    (now_str, wid, repo_id)
                )
                cursor.execute(
                    "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, worker_id) VALUES (%s, %s, %s, %s, %s)",
                    (repo_id, 'pending', 'processing', now_str, wid)
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
        cursor = conn.cursor()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor.execute("""
                SELECT id, owner, repo FROM queue
                WHERE status = 'pending'
                   OR (status = 'processing' AND claimed_at < ?)
                ORDER BY stars DESC
                LIMIT 1
            """, (stale_cutoff,))
            row = cursor.fetchone()
            if row:
                repo_id, owner, repo = row
                cursor.execute(
                    "UPDATE queue SET status = 'processing', claimed_at = ?, worker_id = ? WHERE id = ?",
                    (now_str, wid, repo_id)
                )
                cursor.execute(
                    "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, worker_id) VALUES (?, ?, ?, ?, ?)",
                    (repo_id, 'pending', 'processing', now_str, wid)
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


def update_heartbeat(repo_id, db_path=None):
    """Workers call this periodically to refresh claimed_at, preventing stale reclaim."""
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    now_str = datetime.now(timezone.utc).isoformat()
    if _is_pg(path):
        import psycopg2
        conn = psycopg2.connect(path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE queue SET claimed_at = %s WHERE id = %s AND status = 'processing'",
                (now_str, repo_id)
            )
            conn.commit()
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(path)
        conn.execute(
            "UPDATE queue SET claimed_at = ? WHERE id = ? AND status = 'processing'",
            (now_str, repo_id)
        )
        conn.commit()
        conn.close()


def requeue_stale_processing(db_path=None, stale_timeout_minutes=STALE_TIMEOUT_MINUTES):
    """Reset processing rows whose claimed_at has expired back to pending.

    Returns the number of rows requeued. Call this at crawler startup to
    recover from any previously crashed workers.
    """
    import core.crawler
    path = db_path or core.crawler.DB_PATH
    stale_cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=stale_timeout_minutes)
    ).isoformat()
    now_str = datetime.now(timezone.utc).isoformat()

    if _is_pg(path):
        import psycopg2
        conn = psycopg2.connect(path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE queue SET status = 'pending', worker_id = NULL, claimed_at = NULL
                WHERE status = 'processing' AND claimed_at < %s
                RETURNING id
            """, (stale_cutoff,))
            requeued_ids = [r[0] for r in cursor.fetchall()]
            for rid in requeued_ids:
                cursor.execute(
                    "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, error_msg) VALUES (%s, %s, %s, %s, %s)",
                    (rid, 'processing', 'pending', now_str, 'stale reclaim')
                )
            conn.commit()
            return len(requeued_ids)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM queue
            WHERE status = 'processing' AND claimed_at < ?
        """, (stale_cutoff,))
        stale_ids = [r[0] for r in cursor.fetchall()]
        for rid in stale_ids:
            cursor.execute(
                "UPDATE queue SET status = 'pending', worker_id = NULL, claimed_at = NULL WHERE id = ?",
                (rid,)
            )
            cursor.execute(
                "INSERT INTO transition_history (repo_id, from_status, to_status, transitioned_at, error_msg) VALUES (?, ?, ?, ?, ?)",
                (rid, 'processing', 'pending', now_str, 'stale reclaim')
            )
        conn.commit()
        conn.close()
        return len(stale_ids)
