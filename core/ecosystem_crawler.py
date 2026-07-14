import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.parse
import urllib.error
import zipfile
import shutil
from datetime import datetime, timezone

from adapters.java.extractor import JavaExtractor
from core.shacl_validator import SHACLValidator
from core.agents.coordinator import CoordinatorAgent

DB_PATH = "test_projects/github_benchmarks/crawler_queue.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

class GitHubEcosystemCrawler:
    """Ecosystem-scale GitHub crawler for Java projects with SQLite status queuing and rate limit backoff."""

    def __init__(self, github_token=None):
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.setup_db()

    def setup_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT,
                repo TEXT,
                stars INTEGER,
                tag1 TEXT,
                tag2 TEXT,
                status TEXT DEFAULT 'pending',
                error_msg TEXT,
                processed_at TEXT
            )
        """)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_owner_repo ON queue (owner, repo)")
        conn.commit()
        conn.close()

    def make_github_request(self, url):
        headers = {
            "User-Agent": "IMPACT-Ecosystem-Crawler",
            "Accept": "application/vnd.github.v3+json"
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        req = urllib.request.Request(url, headers=headers)
        retries = 3
        backoff = 5

        while retries > 0:
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    return response.read(), response.info()
            except urllib.error.HTTPError as e:
                # Inspect rate limiting headers
                reset_header = e.headers.get("X-RateLimit-Reset")
                remaining_header = e.headers.get("X-RateLimit-Remaining")
                
                if e.code == 403 and remaining_header == "0":
                    if reset_header:
                        reset_time = int(reset_header)
                        sleep_duration = max(reset_time - int(time.time()) + 2, 5)
                        print(f"[Rate Limit] Limit reached. Sleeping for {sleep_duration} seconds...")
                        time.sleep(sleep_duration)
                        continue
                
                if e.code in [403, 429]:
                    print(f"[Throttled] Status {e.code}. Backing off for {backoff} seconds...")
                    time.sleep(backoff)
                    backoff *= 2
                    retries -= 1
                    continue
                
                print(f"[HTTP Error] {e.code} for URL: {url}")
                return None, None
            except Exception as e:
                print(f"[Network Error] {e}. Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
                retries -= 1

        return None, None

    def discover_java_repos(self, min_stars=500, max_pages=5):
        print(f"Discovering Java repositories on GitHub (min stars: {min_stars})...")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for page in range(1, max_pages + 1):
            url = f"https://api.github.com/search/repositories?q=language:java+stars:>={min_stars}&sort=stars&order=desc&per_page=100&page={page}"
            content, _ = self.make_github_request(url)
            if not content:
                break

            try:
                data = json.loads(content.decode("utf-8"))
                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    full_name = item["full_name"]
                    owner, repo = full_name.split("/")
                    stars = item["stargazers_count"]
                    
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO queue (owner, repo, stars) VALUES (?, ?, ?)",
                            (owner, repo, stars)
                        )
                    except sqlite3.Error:
                        pass
                
                print(f"Discovered and queued repositories from search results page {page}.")
                conn.commit()
            except Exception as e:
                print(f"Error parsing discovery page {page}: {e}")
                break

        conn.close()

    def fetch_adjacent_tags(self, owner, repo):
        url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=10"
        content, _ = self.make_github_request(url)
        if not content:
            return None, None

        try:
            tags_data = json.loads(content.decode("utf-8"))
            if len(tags_data) < 2:
                return None, None
            # Return latest tag and the one right before it
            tag2 = tags_data[0]["name"]
            tag1 = tags_data[1]["name"]
            return tag1, tag2
        except Exception as e:
            print(f"Error parsing tags for {owner}/{repo}: {e}")
            return None, None

    def download_zip(self, owner, repo, tag, output_dir):
        zip_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.zip"
        
        # Try primary tag download
        content, _ = self.make_github_request(zip_url)
        if not content:
            # Fallback to alternate simple version tag
            alternative_tag = tag.split("-")[-1] if "-" in tag else tag
            alt_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{alternative_tag}.zip"
            content, _ = self.make_github_request(alt_url)
            if not content:
                return False, None

        os.makedirs(output_dir, exist_ok=True)
        zip_path = os.path.join(output_dir, f"{tag}.zip")
        with open(zip_path, "wb") as f:
            f.write(content)

        extracted_dir = os.path.join(output_dir, f"extracted_{tag}")
        os.makedirs(extracted_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extracted_dir)
            os.remove(zip_path)
            
            # Find the nested repository folder inside
            for entry in os.listdir(extracted_dir):
                entry_path = os.path.join(extracted_dir, entry)
                if os.path.isdir(entry_path):
                    return True, (entry_path, extracted_dir)
            return True, (extracted_dir, extracted_dir)
        except Exception as e:
            print(f"Zip extraction failed for {tag}: {e}")
            return False, None

    def process_repo(self, repo_id, owner, repo):
        print(f"\nProcessing repository: {owner}/{repo}")
        
        tag1, tag2 = self.fetch_adjacent_tags(owner, repo)
        if not tag1 or not tag2:
            self.mark_status(repo_id, "failed", error_msg="Insufficient release tags found")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE queue SET tag1 = ?, tag2 = ? WHERE id = ?", (tag1, tag2, repo_id))
        conn.commit()
        conn.close()

        language = "java"
        benchmark_root = os.path.join("test_projects/github_benchmarks", language)
        repo_dir = os.path.join(benchmark_root, f"{owner}_{repo}")
        
        # Download and extract versions
        ok1, paths1 = self.download_zip(owner, repo, tag1, repo_dir)
        if not ok1:
            self.mark_status(repo_id, "failed", error_msg=f"Failed to download version {tag1}")
            return
        path1, cleanup1 = paths1

        ok2, paths2 = self.download_zip(owner, repo, tag2, repo_dir)
        if not ok2:
            self.cleanup_path(cleanup1)
            self.mark_status(repo_id, "failed", error_msg=f"Failed to download version {tag2}")
            return
        path2, cleanup2 = paths2

        graph_v1 = os.path.join(repo_dir, f"{tag1}_graph.json")
        graph_v2 = os.path.join(repo_dir, f"{tag2}_graph.json")

        try:
            # Extract dependencies
            print(f"Extracting dependency graphs for {tag1} and {tag2}...")
            ext1 = JavaExtractor(repo, tag1)
            ext1.extract(path1, graph_v1)

            ext2 = JavaExtractor(repo, tag2)
            ext2.extract(path2, graph_v2)

            # Validate SHACL
            validator = SHACLValidator()
            val1 = validator.validate_graph(graph_v1)
            val2 = validator.validate_graph(graph_v2)

            # Run evolution
            print("Running multi-agent evolution analysis...")
            coordinator = CoordinatorAgent()
            intents = ["avoid cyclic dependencies", "minimize changes and complexity increase"]
            report = coordinator.run_analysis(graph_v1, graph_v2, intents)

            report_path = os.path.join(repo_dir, f"{tag1}_to_{tag2}_analysis.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)

            print(f"Successfully evaluated {owner}/{repo}. Conforms: {val2['conforms']}")
            self.mark_status(repo_id, "crawled")
        except Exception as e:
            print(f"Error during processing: {e}")
            self.mark_status(repo_id, "failed", error_msg=str(e))
        finally:
            # Cleanup source code folder immediately to save disk space
            self.cleanup_path(cleanup1)
            self.cleanup_path(cleanup2)

    def cleanup_path(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"Failed to clean up path {path}: {e}")

    def mark_status(self, repo_id, status, error_msg=None):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE queue SET status = ?, error_msg = ?, processed_at = ? WHERE id = ?",
            (status, error_msg, datetime.now(timezone.utc).isoformat(), repo_id)
        )
        conn.commit()
        conn.close()

    def crawl(self, limit=10):
        # Find pending repos in DB
        conn = sqlite3.connect(DB_PATH)
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

def main():
    if len(sys.argv) < 2:
        print("IMPACT Ecosystem Crawler")
        print("Usage:")
        print("  python3 core/ecosystem_crawler.py discover [min_stars] [pages]")
        print("  python3 core/ecosystem_crawler.py run [limit]")
        print("  python3 core/ecosystem_crawler.py status")
        sys.exit(1)

    cmd = sys.argv[1]
    crawler = GitHubEcosystemCrawler()

    if cmd == "discover":
        min_stars = int(sys.argv[2]) if len(sys.argv) > 2 else 500
        pages = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        crawler.discover_java_repos(min_stars=min_stars, max_pages=pages)
        
    elif cmd == "run":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        crawler.crawl(limit=limit)

    elif cmd == "status":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, count(*) FROM queue GROUP BY status")
        rows = cursor.fetchall()
        print("\n=== Crawler Queue Status ===")
        for status, count in rows:
            print(f"- {status}: {count}")
        conn.close()

if __name__ == "__main__":
    main()
