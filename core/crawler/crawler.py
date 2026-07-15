import os
import sqlite3
from core.crawler.database import setup_db, mark_status, requeue_stale_processing
from core.crawler.discovery import discover_java_repos
from core.crawler.downloader import cleanup_path
from core.crawler.processor import process_repo

class GitHubEcosystemCrawler:
    """Ecosystem-scale GitHub crawler for Java projects with SQLite status queuing and rate limit backoff."""

    def __init__(self, github_token=None):
        import core.crawler
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.db_path = core.crawler.DB_PATH
        setup_db(self.db_path)

    def make_github_request(self, url):
        from core.crawler.network import make_github_request
        return make_github_request(url, self.github_token)

    def discover_repos(self, language="java", min_stars=500, max_pages=10, partition_search=True):
        from core.crawler.discovery import discover_repos
        discover_repos(self.github_token, self.db_path, language, min_stars, max_pages, partition_search)

    def discover_java_repos(self, min_stars=500, max_pages=3):
        # Backward-compatible wrapper
        self.discover_repos("java", min_stars, max_pages, partition_search=False)

    def process_repo(self, repo_id, owner, repo):
        process_repo(repo_id, owner, repo, self.github_token, self.db_path)

    def cleanup_path(self, path):
        cleanup_path(path)

    def mark_status(self, repo_id, status, error_msg=None):
        mark_status(repo_id, status, error_msg, self.db_path)

    def crawl(self, limit=10):
        from core.crawler.database import claim_next_pending

        # Recover any rows left stuck in 'processing' by previously crashed workers
        recovered = requeue_stale_processing(self.db_path)
        if recovered:
            print(f"[Queue] Recovered {recovered} stale 'processing' row(s) back to 'pending'.")

        print(f"Starting distributed crawl execution (up to {limit} repositories)...")
        crawled_count = 0
        for _ in range(limit):
            claimed = claim_next_pending(self.db_path)
            if not claimed:
                break

            repo_id, owner, repo = claimed
            crawled_count += 1
            try:
                self.process_repo(repo_id, owner, repo)
            except Exception as e:
                print(f"Fatal error processing {owner}/{repo}: {e}")
                self.mark_status(repo_id, "failed", error_msg=str(e))

        if crawled_count == 0:
            print("No pending repositories in queue database. Run discovery first.")
        else:
            print(f"Crawl run complete. Processed {crawled_count} repositories.")

