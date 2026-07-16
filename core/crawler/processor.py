import os
import sqlite3
import json
from adapters.java.extractor import JavaExtractor
from core.shacl_validator import SHACLValidator
from core.agents.coordinator import CoordinatorAgent
from core.crawler.downloader import download_zip, cleanup_path
from core.crawler.database import mark_status
import core.crawler.network as network

def process_repo(repo_id, owner, repo, github_token, db_path):
    """Retrieves adjacent release tags, downloads code, and runs extraction/analysis."""
    print(f"Processing repository {owner}/{repo} (ID: {repo_id})...")
    
    # Retrieve tags
    tags_url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=10"
    try:
        content, _ = network.make_github_request(tags_url, github_token)
        tags_data = json.loads(content.decode("utf-8"))
    except Exception as e:
        print(f"Failed to fetch tags for {owner}/{repo}: {e}")
        mark_status(repo_id, "failed", error_msg=f"Failed to fetch tags: {e}", db_path=db_path)
        return

    tags = [t["name"] for t in tags_data]
    if len(tags) < 2:
        print(f"Insufficient tags found for {owner}/{repo}. Need at least 2.")
        mark_status(repo_id, "failed", error_msg="Insufficient release tags found", db_path=db_path)
        return

    # Choose two adjacent tags
    tag2, tag1 = tags[0], tags[1]
    print(f"Selected adjacent tags for evolution: {tag1} -> {tag2}")

    if db_path.startswith("postgresql://") or db_path.startswith("postgres://"):
        import psycopg2
        conn = psycopg2.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE queue SET tag1 = %s, tag2 = %s WHERE id = %s", (tag1, tag2, repo_id))
    else:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE queue SET tag1 = ?, tag2 = ? WHERE id = ?", (tag1, tag2, repo_id))
    conn.commit()
    conn.close()

    # Retrieve language from DB
    language = "java"
    if db_path.startswith("postgresql://") or db_path.startswith("postgres://"):
        import psycopg2
        conn = psycopg2.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM queue WHERE id = %s", (repo_id,))
        row = cursor.fetchone()
        if row and row[0]:
            language = row[0]
        conn.close()
    else:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM queue WHERE id = ?", (repo_id,))
        row = cursor.fetchone()
        if row and row[0]:
            language = row[0]
        conn.close()

    benchmark_root = os.path.join("test_projects/github_benchmarks", language)
    repo_dir = os.path.join(benchmark_root, f"{owner}_{repo}")
    
    # Download and extract versions
    ok1, paths1 = download_zip(owner, repo, tag1, repo_dir, github_token)
    if not ok1:
        mark_status(repo_id, "failed", error_msg=f"Failed to download version {tag1}", db_path=db_path)
        return
    path1, cleanup1 = paths1

    ok2, paths2 = download_zip(owner, repo, tag2, repo_dir, github_token)
    if not ok2:
        cleanup_path(cleanup1)
        mark_status(repo_id, "failed", error_msg=f"Failed to download version {tag2}", db_path=db_path)
        return
    path2, cleanup2 = paths2

    graph_v1 = os.path.join(repo_dir, f"{tag1}_graph.json")
    graph_v2 = os.path.join(repo_dir, f"{tag2}_graph.json")

    from datetime import datetime, timezone
    extraction_start = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        # Extract dependencies
        if language == "java":
            print(f"Extracting dependency graphs for {tag1} and {tag2}...")
            ext1 = JavaExtractor(repo, tag1)
            ext1.extract(path1, graph_v1)

            ext2 = JavaExtractor(repo, tag2)
            ext2.extract(path2, graph_v2)
        else:
            raise NotImplementedError(f"Language adapter for '{language}' is not yet implemented.")

        extraction_end = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Save extraction timestamps to DB
        if db_path.startswith("postgresql://") or db_path.startswith("postgres://"):
            import psycopg2
            conn = psycopg2.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE queue SET extraction_start_at = %s, extraction_end_at = %s WHERE id = %s",
                (extraction_start, extraction_end, repo_id)
            )
        else:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE queue SET extraction_start_at = ?, extraction_end_at = ? WHERE id = ?",
                (extraction_start, extraction_end, repo_id)
            )
        conn.commit()
        conn.close()

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

        # Extract and record system metrics, SHACL validation, structural diff, and artifact paths
        try:
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
            
            conforms_v1 = 1 if val1.get("conforms", False) else 0
            conforms_v2 = 1 if val2.get("conforms", False) else 0
            
            from core.agents.diff_agent import DiffAgent
            diff_agent = DiffAgent()
            diff_report = diff_agent.execute(graph_v1, graph_v2)
            added_nodes = diff_report.get("added_nodes_count", 0)
            removed_nodes = diff_report.get("removed_nodes_count", 0)
            added_edges = diff_report.get("added_edges_count", 0)
            removed_edges = diff_report.get("removed_edges_count", 0)
            new_cycles = diff_report.get("new_cycles_count", 0)
            broken_cycles = diff_report.get("broken_cycles_count", 0)
            
            from core.agents.metrics_agent import MetricsAgent
            metrics_agent = MetricsAgent()
            metrics_report = metrics_agent.execute(graph_v2)
            
            hubs_list = [h["id"] for h in metrics_report.get("top_hubs", [])]
            top_hubs = ", ".join(hubs_list)
            
            anoms_list = [f"{a['id']} (coupling: {a['coupling']}, z-score: {a['z_score']})" for a in metrics_report.get("coupling_anomalies", [])]
            coupling_anomalies = ", ".join(anoms_list)
            
            intent_status = "VIOLATION" if "VIOLATION" in report else "CONFORMING"
            
            # Paths relative to the working directory
            g1_rel = os.path.relpath(graph_v1, start=os.getcwd())
            g2_rel = os.path.relpath(graph_v2, start=os.getcwd())
            rep_rel = os.path.relpath(report_path, start=os.getcwd())
            
            if db_path.startswith("postgresql://") or db_path.startswith("postgres://"):
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
                    g1_rel, g2_rel, rep_rel, repo_id
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
                    g1_rel, g2_rel, rep_rel, repo_id
                ))
            conn.commit()
            conn.close()
        except Exception as ex:
            print(f"Warning: failed to extract/save metrics/paths to DB: {ex}")

        print(f"Successfully evaluated {owner}/{repo}. Conforms: {val2['conforms']}")
        mark_status(repo_id, "crawled", db_path=db_path)
    except Exception as e:
        print(f"Error during processing: {e}")
        mark_status(repo_id, "failed", error_msg=str(e), db_path=db_path)
    finally:
        # Cleanup source code folder immediately to save disk space
        cleanup_path(cleanup1)
        cleanup_path(cleanup2)
