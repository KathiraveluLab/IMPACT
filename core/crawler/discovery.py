import sqlite3
import json
import urllib.parse
import core.crawler.network as network

def discover_java_repos(github_token, db_path, min_stars=500, max_pages=3):
    """Discovers popular Java repositories on GitHub and enqueues them."""
    print(f"Discovering Java repositories on GitHub (min stars: {min_stars})...")
    
    for page in range(1, max_pages + 1):
        query = f"language:java stars:>={min_stars}"
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&page={page}&per_page=100"
        
        try:
            content, _ = network.make_github_request(url, github_token)
            data = json.loads(content.decode("utf-8"))
            
            if db_path.startswith("postgresql://") or db_path.startswith("postgres://"):
                import psycopg2
                conn = psycopg2.connect(db_path)
                cursor = conn.cursor()
                for item in data.get("items", []):
                    full_name = item["full_name"]
                    stars = item["stargazers_count"]
                    owner, repo = full_name.split("/")
                    cursor.execute(
                        "INSERT INTO queue (owner, repo, stars) VALUES (%s, %s, %s) ON CONFLICT (owner, repo) DO NOTHING",
                        (owner, repo, stars)
                    )
            else:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                for item in data.get("items", []):
                    full_name = item["full_name"]
                    stars = item["stargazers_count"]
                    owner, repo = full_name.split("/")
                    cursor.execute(
                        "INSERT OR IGNORE INTO queue (owner, repo, stars) VALUES (?, ?, ?)",
                        (owner, repo, stars)
                    )
            conn.commit()
            conn.close()
            print(f"Discovered and queued repositories from search results page {page}.")
        except Exception as e:
            print(f"Failed to discover repositories on page {page}: {e}")
            break
