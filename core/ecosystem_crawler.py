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

    discover_parser = subparsers.add_parser("discover", help="Discover repositories on GitHub")
    discover_parser.add_argument("--language", "-l", type=str, default="java", help="Selected programming language for repository discovery")
    discover_parser.add_argument("--min-stars", type=int, default=500, help="Minimum number of stars for repository discovery")
    discover_parser.add_argument("--pages", type=int, default=10, help="Number of search API pages to retrieve per range (max 10)")
    discover_parser.add_argument("--no-partition", action="store_false", dest="partition", help="Disable star range partitioning (query all stars at once)")

    run_parser = subparsers.add_parser("run", aliases=["crawl"], help="Run evolution analysis crawler execution loop")
    run_parser.add_argument("--limit", type=int, default=-1, help="Maximum number of repositories to crawl in this run (default: unlimited)")

    subparsers.add_parser("status", help="Print crawler database queue stats")
    subparsers.add_parser("export-graphs", help="Export crawled repository graphs as .graph files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    crawler = GitHubEcosystemCrawler()

    if args.command == "discover":
        crawler.discover_repos(
            language=args.language,
            min_stars=args.min_stars,
            max_pages=args.pages,
            partition_search=args.partition
        )
    elif args.command in ("run", "crawl"):
        crawler.crawl(limit=args.limit)
    elif args.command == "export-graphs":
        import os
        from core.graph_utils import export_graph_file
        print("Searching for crawled JSON graph files to export...")
        exported_count = 0
        for root, dirs, files in os.walk("test_projects/github_benchmarks"):
            for file in files:
                if file.endswith("_graph.json"):
                    json_path = os.path.join(root, file)
                    graph_path = json_path.replace(".json", ".graph")
                    try:
                        export_graph_file(json_path, graph_path)
                        print(f"Exported: {graph_path}")
                        exported_count += 1
                    except Exception as e:
                        print(f"Failed to export {json_path}: {e}", file=sys.stderr)
        print(f"Successfully exported {exported_count} .graph files.")
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
