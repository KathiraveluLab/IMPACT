import sqlite3
import json
import urllib.parse
import core.crawler.network as network

def discover_repos(github_token, db_path, language="java", min_stars=500, max_pages=10, partition_search=True):
    """Discovers repositories on GitHub for a selected language and enqueues them."""
    print(f"Discovering {language} repositories on GitHub (min stars: {min_stars}, partition: {partition_search})...")
    
    if partition_search:
        # Generate partitions based on stars to bypass the 1,000 results limit of Search API
        ranges = []
        current = min_stars
        # Steps grow dynamically to capture both high-density (low stars) and low-density (high stars) zones
        steps = [50, 50, 100, 100, 200, 200, 300, 500, 1000, 2000, 5000, 10000, 30000]
        for step in steps:
            ranges.append((current, current + step))
            current = current + step + 1
        ranges.append((current, None))
    else:
        ranges = [(min_stars, None)]

    for low, high in ranges:
        if high is not None:
            star_query = f"{low}..{high}"
        else:
            star_query = f">={low}"
            
        print(f"Querying star range: {star_query}")
        
        for page in range(1, max_pages + 1):
            query = f"language:{language} stars:{star_query}"
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&page={page}&per_page=100"
            
            try:
                content, _ = network.make_github_request(url, github_token)
                data = json.loads(content.decode("utf-8"))
                
                items = data.get("items", [])
                if not items:
                    print(f"No more items found for range {star_query} at page {page}.")
                    break
                    
                if db_path.startswith("postgresql://") or db_path.startswith("postgres://"):
                    import psycopg2
                    conn = psycopg2.connect(db_path)
                    cursor = conn.cursor()
                    for item in items:
                        full_name = item["full_name"]
                        stars = item["stargazers_count"]
                        owner, repo = full_name.split("/")
                        cursor.execute(
                            """
                            INSERT INTO queue (owner, repo, stars, language) VALUES (%s, %s, %s, %s)
                            ON CONFLICT (owner, repo) DO UPDATE SET stars = EXCLUDED.stars, language = EXCLUDED.language
                            """,
                            (owner, repo, stars, language)
                        )
                else:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    for item in items:
                        full_name = item["full_name"]
                        stars = item["stargazers_count"]
                        owner, repo = full_name.split("/")
                        cursor.execute(
                            """
                            INSERT INTO queue (owner, repo, stars, language) VALUES (?, ?, ?, ?)
                            ON CONFLICT(owner, repo) DO UPDATE SET stars=excluded.stars, language=excluded.language
                            """,
                            (owner, repo, stars, language)
                        )
                conn.commit()
                conn.close()
                print(f"Discovered and queued {len(items)} repositories from search results page {page} for range {star_query}.")
                
                if len(items) < 100:
                    # Received fewer than 100 items; this partition is fully exhausted
                    break
            except Exception as e:
                print(f"Failed to discover repositories on page {page} for range {star_query}: {e}")
                break

def discover_java_repos(github_token, db_path, min_stars=500, max_pages=3):
    """Backward-compatible wrapper for Java repository discovery."""
    discover_repos(github_token, db_path, language="java", min_stars=min_stars, max_pages=max_pages, partition_search=False)
