#!/usr/bin/env python3
import os
import sys
import csv
import sqlite3
import argparse
import core.crawler

def is_pg(path):
    return path.startswith("postgresql://") or path.startswith("postgres://")

def main():
    parser = argparse.ArgumentParser(description="Export crawled repositories from the IMPACT queue database.")
    parser.add_argument("--output", "-o", default="crawled_repos.csv", help="Path to output CSV file (default: crawled_repos.csv)")
    parser.add_argument("--all", action="store_true", help="Export all repositories, not just completed ('crawled') ones")
    args = parser.parse_args()

    db_path = core.crawler.DB_PATH
    print(f"Connecting to database: {db_path}")

    query = "SELECT id, owner, repo, stars, tag1, tag2, status, processed_at, language, error_msg FROM queue"
    if not args.all:
        query += " WHERE status = 'crawled'"
    query += " ORDER BY processed_at DESC"

    try:
        if is_pg(db_path):
            import psycopg2
            conn = psycopg2.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]
            conn.close()
        else:
            if not os.path.exists(db_path):
                print(f"Database file not found: {db_path}", file=sys.stderr)
                sys.exit(1)
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]
            conn.close()

        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        status_desc = "all" if args.all else "completed ('crawled')"
        print(f"Successfully exported {len(rows)} {status_desc} repositories to {args.output}")

    except Exception as e:
        print(f"Error exporting data: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
