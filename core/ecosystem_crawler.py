# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "javalang",
#     "networkx",
#     "pyshacl",
#     "rdflib",
# ]
# ///

import sys
import sqlite3
from core.crawler import GitHubEcosystemCrawler, DB_PATH

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="IMPACT Ecosystem Crawler - Resilient repository crawler and AST evolution extractor."
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    discover_parser = subparsers.add_parser("discover", help="Discover Java repositories on GitHub")
    discover_parser.add_argument("--min-stars", type=int, default=500, help="Minimum number of stars for repository discovery")
    discover_parser.add_argument("--pages", type=int, default=3, help="Number of search API pages to retrieve")

    run_parser = subparsers.add_parser("run", help="Run evolution analysis crawler execution loop")
    run_parser.add_argument("--limit", type=int, default=5, help="Maximum number of repositories to crawl in this run")

    subparsers.add_parser("status", help="Print crawler database queue stats")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    crawler = GitHubEcosystemCrawler()

    if args.command == "discover":
        crawler.discover_java_repos(min_stars=args.min_stars, max_pages=args.pages)
    elif args.command == "run":
        crawler.crawl(limit=args.limit)
    elif args.command == "status":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, count(*) FROM queue GROUP BY status")
        rows = cursor.fetchall()
        print("\n=== Crawler Queue Status ===")
        for status, count in rows:
            print(f"- {status}: {count}")
        
        cursor.execute("""
            SELECT h.transitioned_at, q.owner, q.repo, h.from_status, h.to_status, h.error_msg
            FROM transition_history h
            JOIN queue q ON h.repo_id = q.id
            ORDER BY h.transitioned_at DESC
            LIMIT 10
        """)
        history_rows = cursor.fetchall()
        if history_rows:
            print("\n=== State Transition History (Recent) ===")
            for transitioned_at, owner, repo, from_status, to_status, error_msg in history_rows:
                err_suffix = f" (Error: {error_msg})" if error_msg else ""
                print(f"[{transitioned_at}] {owner}/{repo}: {from_status} -> {to_status}{err_suffix}")
        else:
            print("\nNo transition history recorded yet.")
        conn.close()

if __name__ == "__main__":
    main()
