#!/usr/bin/env python3
"""
Database Migration and Schema Integrity Test.
Simulates database schema migrations for the crawler queue database,
verifying that existing items are preserved while new columns/indices are created.
"""

import os
import sqlite3
import unittest
import tempfile

class TestDbMigration(unittest.TestCase):
    def setUp(self):
        # Create a temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_migration_flow(self):
        print("\n--- Running DB Migration Tests ---")
        
        # Step 1: Create V1 schema
        print("[Schema V1] Creating legacy crawler queue schema...")
        self.cursor.execute("""
            CREATE TABLE crawler_queue (
                repository TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
        """)
        self.conn.commit()
        
        # Insert legacy records
        self.cursor.execute("INSERT INTO crawler_queue VALUES ('jhy/jsoup', 'crawled')")
        self.cursor.execute("INSERT INTO crawler_queue VALUES ('google/gson', 'pending')")
        self.conn.commit()
        
        # Verify legacy data
        self.cursor.execute("SELECT COUNT(*) FROM crawler_queue")
        self.assertEqual(self.cursor.fetchone()[0], 2)
        
        # Step 2: Apply Migration to V2 (adding transition timestamps and worker_id)
        print("[Schema V2] Applying migration schema updates...")
        try:
            self.cursor.execute("ALTER TABLE crawler_queue ADD COLUMN worker_id TEXT")
            self.cursor.execute("ALTER TABLE crawler_queue ADD COLUMN updated_at TIMESTAMP")
            self.conn.commit()
            print("[Migration] Columns added successfully.")
        except Exception as e:
            self.fail(f"Failed to alter table: {e}")
            
        # Insert or update data using new columns
        self.cursor.execute("""
            UPDATE crawler_queue 
            SET worker_id = 'worker-1', updated_at = CURRENT_TIMESTAMP 
            WHERE repository = 'jhy/jsoup'
        """)
        self.conn.commit()
        
        # Verify migrated data structure
        self.cursor.execute("SELECT repository, status, worker_id, updated_at FROM crawler_queue WHERE repository = 'jhy/jsoup'")
        row = self.cursor.fetchone()
        self.assertEqual(row[0], 'jhy/jsoup')
        self.assertEqual(row[1], 'crawled')
        self.assertEqual(row[2], 'worker-1')
        self.assertIsNotNone(row[3])
        
        print("[Schema V2] Schema validation and data integrity preserved.")

if __name__ == "__main__":
    unittest.main()
