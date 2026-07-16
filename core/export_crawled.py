#!/usr/bin/env python3
import os
import sys
import csv
import sqlite3
import argparse
import core.crawler

def is_pg(path):
    return path.startswith("postgresql://") or path.startswith("postgres://")

def harvest_missing_metrics(db_path):
    print("Checking for completed crawls with missing metrics to harvest retroactively...")
    # Fetch completed crawls where loc_v1 is null
    query = "SELECT id, owner, repo, tag1, tag2, language FROM queue WHERE status = 'crawled' AND loc_v1 IS NULL"
    rows = []
    try:
        if is_pg(db_path):
            import psycopg2
            conn = psycopg2.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
        else:
            if not os.path.exists(db_path):
                return
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
    except Exception as e:
        print(f"Failed to fetch missing metrics queue: {e}", file=sys.stderr)
        return

    if not rows:
        print("No missing metrics to harvest.")
        return

    print(f"Found {len(rows)} repositories to harvest.")
    from core.shacl_validator import SHACLValidator
    from core.agents.diff_agent import DiffAgent
    from core.agents.metrics_agent import MetricsAgent
    import json

    validator = SHACLValidator()
    diff_agent = DiffAgent()
    metrics_agent = MetricsAgent()

    for r_id, owner, repo, tag1, tag2, language in rows:
        lang = language if language else "java"
        benchmark_root = os.path.join("test_projects/github_benchmarks", lang)
        repo_dir = os.path.join(benchmark_root, f"{owner}_{repo}")
        graph_v1 = os.path.join(repo_dir, f"{tag1}_graph.json")
        graph_v2 = os.path.join(repo_dir, f"{tag2}_graph.json")
        report_path = os.path.join(repo_dir, f"{tag1}_to_{tag2}_analysis.txt")

        if not (os.path.exists(graph_v1) and os.path.exists(graph_v2)):
            print(f"Skipping {owner}/{repo}: JSON graph files do not exist locally.")
            continue

        try:
            print(f"Harvesting metrics for {owner}/{repo} ({tag1} -> {tag2})...")
            with open(graph_v1, "r", encoding="utf-8") as f:
                g1_data = json.load(f)
            with open(graph_v2, "r", encoding="utf-8") as f:
                g2_data = json.load(f)

            m1 = g1_data.get("systemMetrics", {})
            m2 = g2_data.get("systemMetrics", {})

            loc_v1 = m1.get("totalLinesOfCode", 0)
            loc_v2 = m2.get("totalLinesOfCode", 0)
            classes_v1 = m1.get("totalClasses", 0)
            classes_v2 = m2.get("totalClasses", 0)
            coupling_v1 = m1.get("averageCoupling", 0.0)
            coupling_v2 = m2.get("averageCoupling", 0.0)

            val1 = validator.validate_graph(graph_v1)
            val2 = validator.validate_graph(graph_v2)
            conforms_v1 = 1 if val1.get("conforms", False) else 0
            conforms_v2 = 1 if val2.get("conforms", False) else 0

            diff_report = diff_agent.execute(graph_v1, graph_v2)
            added_nodes = diff_report.get("added_nodes_count", 0)
            removed_nodes = diff_report.get("removed_nodes_count", 0)
            added_edges = diff_report.get("added_edges_count", 0)
            removed_edges = diff_report.get("removed_edges_count", 0)
            new_cycles = diff_report.get("new_cycles_count", 0)
            broken_cycles = diff_report.get("broken_cycles_count", 0)

            metrics_report = metrics_agent.execute(graph_v2)
            hubs_list = [h["id"] for h in metrics_report.get("top_hubs", [])]
            top_hubs = ", ".join(hubs_list)
            
            anoms_list = [f"{a['id']} (coupling: {a['coupling']}, z-score: {a['z_score']})" for a in metrics_report.get("coupling_anomalies", [])]
            coupling_anomalies = ", ".join(anoms_list)

            report = ""
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    report = f.read()

            intent_status = "VIOLATION" if "VIOLATION" in report else "CONFORMING"

            g1_rel = os.path.relpath(graph_v1, start=os.getcwd())
            g2_rel = os.path.relpath(graph_v2, start=os.getcwd())
            rep_rel = os.path.relpath(report_path, start=os.getcwd()) if os.path.exists(report_path) else None

            if is_pg(db_path):
                import psycopg2
                conn = psycopg2.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE queue SET
                        loc_v1 = %s, loc_v2 = %s,
                        classes_v1 = %s, classes_v2 = %s,
                        coupling_v1 = %s, coupling_v2 = %s,
                        conforms_v1 = %s, conforms_v2 = %s,
                        added_nodes = %s, removed_nodes = %s,
                        added_edges = %s, removed_edges = %s,
                        new_cycles = %s, broken_cycles = %s,
                        intent_status = %s,
                        top_hubs = %s, coupling_anomalies = %s,
                        report_content = %s,
                        graph_v1_path = %s, graph_v2_path = %s,
                        report_path = %s
                    WHERE id = %s
                """, (
                    loc_v1, loc_v2, classes_v1, classes_v2,
                    coupling_v1, coupling_v2, bool(conforms_v1), bool(conforms_v2),
                    added_nodes, removed_nodes, added_edges, removed_edges,
                    new_cycles, broken_cycles, intent_status,
                    top_hubs, coupling_anomalies, report,
                    g1_rel, g2_rel, rep_rel, r_id
                ))
            else:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE queue SET
                        loc_v1 = ?, loc_v2 = ?,
                        classes_v1 = ?, classes_v2 = ?,
                        coupling_v1 = ?, coupling_v2 = ?,
                        conforms_v1 = ?, conforms_v2 = ?,
                        added_nodes = ?, removed_nodes = ?,
                        added_edges = ?, removed_edges = ?,
                        new_cycles = ?, broken_cycles = ?,
                        intent_status = ?,
                        top_hubs = ?, coupling_anomalies = ?,
                        report_content = ?,
                        graph_v1_path = ?, graph_v2_path = ?,
                        report_path = ?
                    WHERE id = ?
                """, (
                    loc_v1, loc_v2, classes_v1, classes_v2,
                    coupling_v1, coupling_v2, conforms_v1, conforms_v2,
                    added_nodes, removed_nodes, added_edges, removed_edges,
                    new_cycles, broken_cycles, intent_status,
                    top_hubs, coupling_anomalies, report,
                    g1_rel, g2_rel, rep_rel, r_id
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error harvesting metrics for {owner}/{repo}: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Export crawled repositories from the IMPACT queue database.")
    parser.add_argument("--output", "-o", default="crawled_repos.csv", help="Path to output CSV file (default: crawled_repos.csv)")
    parser.add_argument("--all", action="store_true", help="Export all repositories, not just completed ('crawled') ones")
    parser.add_argument("--graphs", "-g", action="store_true", help="Export crawled repository graphs to .graph files instead of CSV")
    args = parser.parse_args()

    db_path = core.crawler.DB_PATH
    print(f"Connecting to database: {db_path}")

    # Set up database (creates table/applies migrations if needed)
    from core.crawler.database import setup_db
    setup_db(db_path)

    if args.graphs:
        export_graphs(db_path, args.all)
        return

    # Harvest metrics retroactively if needed
    harvest_missing_metrics(db_path)

    query = (
        "SELECT id, owner, repo, stars, tag1, tag2, status, processed_at, language, "
        "extraction_start_at, extraction_end_at, loc_v1, loc_v2, classes_v1, classes_v2, "
        "coupling_v1, coupling_v2, conforms_v1, conforms_v2, added_nodes, removed_nodes, "
        "added_edges, removed_edges, new_cycles, broken_cycles, intent_status, "
        "top_hubs, coupling_anomalies, report_content, "
        "graph_v1_path, graph_v2_path, report_path, error_msg FROM queue"
    )
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

def export_graphs(db_path, all_repos=False):
    """Queries the database and exports the JSON graphs of crawled repositories to .graph files."""
    query = "SELECT id, owner, repo, graph_v1_path, graph_v2_path FROM queue"
    if not all_repos:
        query += " WHERE status = 'crawled'"

    try:
        if is_pg(db_path):
            import psycopg2
            conn = psycopg2.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
        else:
            if not os.path.exists(db_path):
                print(f"Database file not found: {db_path}", file=sys.stderr)
                return
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

        from core.graph_utils import export_graph_file
        exported_count = 0

        for r_id, owner, repo, g1_path, g2_path in rows:
            for g_path in (g1_path, g2_path):
                if g_path and os.path.exists(g_path):
                    graph_path = g_path.replace(".json", ".graph")
                    try:
                        export_graph_file(g_path, graph_path)
                        exported_count += 1
                    except Exception as e:
                        print(f"Failed to export {g_path}: {e}", file=sys.stderr)

        print(f"Successfully exported {exported_count} .graph files based on database entries.")

    except Exception as e:
        print(f"Error exporting graphs: {e}", file=sys.stderr)

def export_graphs_cli():
    parser = argparse.ArgumentParser(description="Export crawled repository JSON graphs to human-readable .graph files.")
    parser.add_argument("--all", action="store_true", help="Process all repositories, not just completed ('crawled') ones")
    args = parser.parse_args()

    db_path = core.crawler.DB_PATH
    print(f"Connecting to database: {db_path}")

    from core.crawler.database import setup_db
    setup_db(db_path)

    export_graphs(db_path, args.all)

if __name__ == "__main__":
    # Check if --graphs or -g is passed to the main tool
    if "--graphs" in sys.argv or "-g" in sys.argv:
        # Intercept and run export graphs instead
        parser = argparse.ArgumentParser(description="Export crawled repositories/graphs from the IMPACT queue database.")
        parser.add_argument("--graphs", "-g", action="store_true", help="Export graphs to .graph files")
        parser.add_argument("--all", action="store_true", help="Export all repositories, not just completed ('crawled') ones")
        args, _ = parser.parse_known_args()
        
        db_path = core.crawler.DB_PATH
        from core.crawler.database import setup_db
        setup_db(db_path)
        export_graphs(db_path, args.all)
    else:
        main()
