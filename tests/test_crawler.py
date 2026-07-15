import unittest
import os
import sqlite3
import shutil
import tempfile
import json
import time
from unittest.mock import patch, MagicMock

# Temporarily override DB path for testing before importing
import core.crawler
import core.ecosystem_crawler as ec

TEST_DB_PATH = "test_projects/github_benchmarks/test_crawler_queue.db"
core.crawler.DB_PATH = TEST_DB_PATH
ec.DB_PATH = TEST_DB_PATH

class TestGitHubEcosystemCrawler(unittest.TestCase):

    def setUp(self):
        # Override the database path in the module to avoid mutating the main crawler database
        self.original_db_path = core.crawler.DB_PATH
        core.crawler.DB_PATH = TEST_DB_PATH
        ec.DB_PATH = TEST_DB_PATH
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        
        self.crawler = ec.GitHubEcosystemCrawler(github_token="fake_token")

    def tearDown(self):
        core.crawler.DB_PATH = self.original_db_path
        ec.DB_PATH = self.original_db_path
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def test_database_initialization(self):
        """Verify that the SQLite queue table is correctly initialized."""
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(queue)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()

        expected_columns = ["id", "owner", "repo", "stars", "tag1", "tag2", "status", "error_msg", "processed_at"]
        for col in expected_columns:
            self.assertIn(col, columns)

    def test_unique_repository_constraint(self):
        """Verify that inserting duplicate repositories is ignored."""
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        # Try inserting the same owner/repo twice
        cursor.execute("INSERT OR IGNORE INTO queue (owner, repo, stars) VALUES ('test_owner', 'test_repo', 100)")
        cursor.execute("INSERT OR IGNORE INTO queue (owner, repo, stars) VALUES ('test_owner', 'test_repo', 200)")
        conn.commit()

        cursor.execute("SELECT count(*) FROM queue WHERE owner='test_owner' AND repo='test_repo'")
        count = cursor.fetchone()[0]
        
        # Verify only the first one was saved and no crash happened
        self.assertEqual(count, 1)
        
        cursor.execute("SELECT stars FROM queue WHERE owner='test_owner' AND repo='test_repo'")
        stars = cursor.fetchone()[0]
        self.assertEqual(stars, 100)
        conn.close()

    def test_status_transitions(self):
        """Test status changes from pending to crawled or failed."""
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queue (owner, repo, stars) VALUES ('owner_x', 'repo_x', 500)")
        repo_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Mark crawled
        self.crawler.mark_status(repo_id, "crawled")
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, error_msg, processed_at FROM queue WHERE id=?", (repo_id,))
        status, error_msg, processed_at = cursor.fetchone()
        self.assertEqual(status, "crawled")
        self.assertIsNone(error_msg)
        self.assertIsNotNone(processed_at)
        
        # Mark failed with error
        self.crawler.mark_status(repo_id, "failed", error_msg="Timeout reading zip")
        cursor.execute("SELECT status, error_msg FROM queue WHERE id=?", (repo_id,))
        status, error_msg = cursor.fetchone()
        self.assertEqual(status, "failed")
        self.assertEqual(error_msg, "Timeout reading zip")
        conn.close()

    @patch("core.crawler.network.make_github_request")
    def test_repository_discovery(self, mock_request):
        """Test parsing and queueing search discovery results."""
        fake_api_response = {
            "items": [
                {"full_name": "google/guava", "stargazers_count": 48000},
                {"full_name": "junit-team/junit5", "stargazers_count": 9000}
            ]
        }
        mock_request.return_value = (json_bytes := bytes(json.dumps(fake_api_response), "utf-8"), None)
        
        self.crawler.discover_java_repos(min_stars=5000, max_pages=1)

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT owner, repo, stars FROM queue ORDER BY stars DESC")
        rows = cursor.fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ("google", "guava", 48000))
        self.assertEqual(rows[1], ("junit-team", "junit5", 9000))

    def test_cleanup_path(self):
        """Test clean_up helper deletes directories and files."""
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "dummy.txt")
        with open(temp_file, "w") as f:
            f.write("test")

        self.assertTrue(os.path.exists(temp_file))
        self.crawler.cleanup_path(temp_dir)
        self.assertFalse(os.path.exists(temp_dir))

    @patch("urllib.request.urlopen")
    def test_rate_limiting_wait(self, mock_urlopen):
        """Test that crawler handles rate-limiting backoff headers."""
        # Setup fake rate limit HTTPError
        from urllib.error import HTTPError
        from io import BytesIO

        mock_headers = MagicMock()
        mock_headers.get.side_effect = lambda key: {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 1)  # reset in 1 second
        }.get(key)

        fake_error = HTTPError("url", 403, "Forbidden", mock_headers, BytesIO(b"{}"))
        
        # Setup fake urlopen return context manager
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = b'{"ok": true}'
        mock_response.__enter__.return_value.info.return_value = {}

        mock_urlopen.side_effect = [fake_error, mock_response]

        # Call with a patch to sleep to avoid real wait time
        with patch("time.sleep") as mock_sleep:
            content, _ = self.crawler.make_github_request("https://api.github.com/test")
            self.assertEqual(content, b'{"ok": true}')
            mock_sleep.assert_called_once()
            # Assert slept for at least the delta reset time + 2s buffer
            slept_duration = mock_sleep.call_args[0][0]
            self.assertGreaterEqual(slept_duration, 2)

    def test_transition_history(self):
        """Verify that state transitions are recorded in the history table."""
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queue (owner, repo, stars) VALUES ('owner_y', 'repo_y', 600)")
        repo_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.crawler.mark_status(repo_id, "crawled")
        self.crawler.mark_status(repo_id, "failed", error_msg="Validation failed")

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT from_status, to_status, error_msg FROM transition_history WHERE repo_id=? ORDER BY id ASC", (repo_id,))
        transitions = cursor.fetchall()
        conn.close()

        self.assertEqual(len(transitions), 2)
        self.assertEqual(transitions[0], ("pending", "crawled", None))
        self.assertEqual(transitions[1], ("crawled", "failed", "Validation failed"))

    def test_concurrent_claims(self):
        """Verify that multiple concurrent threads claiming repositories do not receive duplicates."""
        import threading
        from core.crawler.database import claim_next_pending

        # Seed 20 pending repositories in the queue
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        for i in range(20):
            cursor.execute(
                "INSERT INTO queue (owner, repo, stars) VALUES (?, ?, ?)",
                (f"owner_{i}", f"repo_{i}", 100 + i)
            )
        conn.commit()
        conn.close()

        claimed_by_thread_1 = []
        claimed_by_thread_2 = []

        def worker(target_list):
            while True:
                claimed = claim_next_pending(TEST_DB_PATH)
                if not claimed:
                    break
                target_list.append(claimed[0])  # Store repo_id
                time.sleep(0.01)

        t1 = threading.Thread(target=worker, args=(claimed_by_thread_1,))
        t2 = threading.Thread(target=worker, args=(claimed_by_thread_2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Check total claimed
        total_claimed = len(claimed_by_thread_1) + len(claimed_by_thread_2)
        self.assertEqual(total_claimed, 20)

        # Check mutual exclusivity
        set1 = set(claimed_by_thread_1)
        set2 = set(claimed_by_thread_2)
        intersection = set1.intersection(set2)
        self.assertEqual(len(intersection), 0, f"Duplicate claims detected: {intersection}")

    def test_worker_id_tracking(self):
        """Verify that worker_id is tracked on claim and in transition history."""
        from core.crawler.database import claim_next_pending, _worker_id
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queue (owner, repo, stars) VALUES ('owner_worker', 'repo_worker', 700)")
        repo_id = cursor.lastrowid
        conn.commit()
        conn.close()

        claimed = claim_next_pending(TEST_DB_PATH)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed[0], repo_id)

        # Verify worker_id in queue table
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT worker_id, claimed_at FROM queue WHERE id=?", (repo_id,))
        worker_id, claimed_at = cursor.fetchone()
        expected_worker_id = _worker_id()
        self.assertEqual(worker_id, expected_worker_id)
        self.assertIsNotNone(claimed_at)

        # Verify worker_id in transition_history table
        cursor.execute("SELECT worker_id FROM transition_history WHERE repo_id=? ORDER BY id DESC LIMIT 1", (repo_id,))
        history_worker_id = cursor.fetchone()[0]
        self.assertEqual(history_worker_id, expected_worker_id)
        conn.close()

    def test_heartbeat_update(self):
        """Verify that update_heartbeat updates the claimed_at timestamp."""
        from core.crawler.database import claim_next_pending, update_heartbeat
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO queue (owner, repo, stars) VALUES ('owner_hb', 'repo_hb', 800)")
        repo_id = cursor.lastrowid
        conn.commit()
        conn.close()

        claimed = claim_next_pending(TEST_DB_PATH)
        self.assertIsNotNone(claimed)

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT claimed_at FROM queue WHERE id=?", (repo_id,))
        first_claimed_at = cursor.fetchone()[0]
        conn.close()

        # Wait a small bit or just call update_heartbeat and check it updates
        time.sleep(0.1)
        update_heartbeat(repo_id, TEST_DB_PATH)

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT claimed_at FROM queue WHERE id=?", (repo_id,))
        second_claimed_at = cursor.fetchone()[0]
        conn.close()

        self.assertNotEqual(first_claimed_at, second_claimed_at)

    def test_reclaim_stale_processing(self):
        """Verify that stale processing rows are reclaimed back to pending."""
        from core.crawler.database import requeue_stale_processing, claim_next_pending
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        # Insert a row that was claimed a long time ago (stale)
        from datetime import datetime, timezone, timedelta
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        cursor.execute(
            "INSERT INTO queue (owner, repo, stars, status, claimed_at, worker_id) VALUES (?, ?, ?, ?, ?, ?)",
            ('owner_stale', 'repo_stale', 900, 'processing', stale_time, 'old_worker')
        )
        repo_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Run requeue_stale_processing
        requeued = requeue_stale_processing(TEST_DB_PATH, stale_timeout_minutes=30)
        self.assertEqual(requeued, 1)

        # Verify database status is pending and worker_id/claimed_at are cleared
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, worker_id, claimed_at FROM queue WHERE id=?", (repo_id,))
        status, worker_id, claimed_at = cursor.fetchone()
        self.assertEqual(status, 'pending')
        self.assertIsNone(worker_id)
        self.assertIsNone(claimed_at)

        # Verify transition history recorded the stale reclaim
        cursor.execute("SELECT from_status, to_status, error_msg FROM transition_history WHERE repo_id=? ORDER BY id DESC LIMIT 1", (repo_id,))
        history = cursor.fetchone()
        self.assertEqual(history, ('processing', 'pending', 'stale reclaim'))
        conn.close()

        # Now test that claim_next_pending can also claim it
        claimed = claim_next_pending(TEST_DB_PATH, stale_timeout_minutes=30)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed[0], repo_id)

    @patch("core.crawler.network.make_github_request")
    def test_partitioned_repository_discovery(self, mock_request):
        """Test partitioned repository discovery with custom language and star slicing."""
        fake_api_response = {
            "items": [
                {"full_name": "python/cpython", "stargazers_count": 60000}
            ]
        }
        mock_request.return_value = (bytes(json.dumps(fake_api_response), "utf-8"), None)
        
        self.crawler.discover_repos(language="python", min_stars=50000, max_pages=1, partition_search=True)

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT owner, repo, stars, language FROM queue WHERE language='python'")
        rows = cursor.fetchall()
        conn.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], ("python", "cpython", 60000, "python"))

    @patch("urllib.request.urlopen")
    def test_retry_after_rate_limiting(self, mock_urlopen):
        """Test that crawler respects the Retry-After header for secondary rate limits."""
        from urllib.error import HTTPError
        from io import BytesIO

        mock_headers = MagicMock()
        mock_headers.get.side_effect = lambda key: {
            "Retry-After": "4"
        }.get(key)

        fake_error = HTTPError("url", 429, "Too Many Requests", mock_headers, BytesIO(b"{}"))
        
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = b'{"ok": true}'
        mock_response.__enter__.return_value.info.return_value = {}

        mock_urlopen.side_effect = [fake_error, mock_response]

        with patch("time.sleep") as mock_sleep:
            content, _ = self.crawler.make_github_request("https://api.github.com/test")
            self.assertEqual(content, b'{"ok": true}')
            mock_sleep.assert_called_once()
            # Assert slept for the Retry-After duration + 2s buffer
            slept_duration = mock_sleep.call_args[0][0]
            self.assertEqual(slept_duration, 6)

if __name__ == "__main__":
    unittest.main()
