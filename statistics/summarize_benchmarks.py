import os
import json

base_dir = "test_projects/github_benchmarks/java"
projects = os.listdir(base_dir)

print(f"{'Project Folder':<38} | {'Project Name':<30} | {'Classes':<7} | {'Edges/Deps':<10} | {'LOC':<8} | {'Avg Coupling':<12}")
print("-" * 120)

for proj in sorted(projects):
    proj_path = os.path.join(base_dir, proj)
    if not os.path.isdir(proj_path):
        continue
    
    files = os.listdir(proj_path)
    for f in sorted(files):
        if f.endswith("_graph.json"):
            file_path = os.path.join(proj_path, f)
            try:
                with open(file_path, 'r') as fh:
                    data = json.load(fh)
                
                proj_name = data.get("projectName", "N/A")
                sys_metrics = data.get("systemMetrics", {})
                total_classes = sys_metrics.get("totalClasses", 0)
                total_loc = sys_metrics.get("totalLinesOfCode", 0)
                avg_coupling = sys_metrics.get("averageCoupling", 0)
                
                # Count edges in nodes dependencies
                nodes = data.get("nodes", [])
                edges_count = sum(len(node.get("dependencies", [])) for node in nodes if isinstance(node, dict))
                
                # Or check if there's a top-level "edges" field
                top_edges = data.get("edges", [])
                if top_edges:
                    edges_count = len(top_edges)
                
                # Let's count cycles if possible or read any summary/reports
                print(f"{proj:<38} | {proj_name:<30} | {total_classes:<7} | {edges_count:<10} | {total_loc:<8} | {avg_coupling:<12.3f}")
            except Exception as e:
                print(f"Error reading {f}: {e}")
