import os
import sqlite3
from core.crawler.database import setup_db, mark_status
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

    def discover_java_repos(self, min_stars=500, max_pages=3):
        discover_java_repos(self.github_token, self.db_path, min_stars, max_pages)

    def process_repo(self, repo_id, owner, repo):
        process_repo(repo_id, owner, repo, self.github_token, self.db_path)

    def cleanup_path(self, path):
        cleanup_path(path)

    def mark_status(self, repo_id, status, error_msg=None):
        mark_status(repo_id, status, error_msg, self.db_path)

    def crawl(self, limit=10):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, owner, repo FROM queue WHERE status = 'pending' ORDER BY stars DESC LIMIT ?", (limit,))
        pending = cursor.fetchall()
        conn.close()

        if not pending:
            print("No pending repositories in queue database. Run discovery first.")
            return

        print(f"Starting crawl execution for {len(pending)} repositories...")
        for repo_id, owner, repo in pending:
            try:
                self.process_repo(repo_id, owner, repo)
            except Exception as e:
                print(f"Fatal error processing {owner}/{repo}: {e}")
                self.mark_status(repo_id, "failed", error_msg=str(e))
