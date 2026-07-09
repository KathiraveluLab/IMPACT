import json
import os

class PMDIntegration:
    """Parses PMD static analysis reports and merges violations into the IMPACT graph."""

    def merge_pmd_report(self, graph_json_path: str, pmd_json_path: str):
        if not os.path.exists(graph_json_path):
            raise FileNotFoundError(f"Graph file not found: {graph_json_path}")
            
        # If no PMD report exists, we simulate a mock clean run or print message
        if not os.path.exists(pmd_json_path):
            print(f"[PMDIntegration] PMD report {pmd_json_path} not found. Skipping static analysis merge.")
            return

        with open(graph_json_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        with open(pmd_json_path, "r", encoding="utf-8") as f:
            pmd_data = json.load(f)

        # Parse PMD violations
        file_violations = {}
        for pmd_file in pmd_data.get("files", []):
            # Normalize path
            rel_path = os.path.basename(pmd_file.get("filename", ""))
            violations = []
            for v in pmd_file.get("violations", []):
                violations.append({
                    "rule": v.get("rule"),
                    "ruleset": v.get("ruleset"),
                    "priority": v.get("priority"),
                    "beginLine": v.get("beginLine"),
                    "message": v.get("message")
                })
            file_violations[rel_path] = violations

        # Merge violations into matching graph nodes
        merged_count = 0
        for node in graph_data.get("nodes", []):
            file_name = os.path.basename(node.get("filePath", ""))
            if file_name in file_violations:
                node["staticAnalysisViolations"] = file_violations[file_name]
                node["metrics"]["staticAnalysisViolationsCount"] = len(file_violations[file_name])
                merged_count += len(file_violations[file_name])
            else:
                node["staticAnalysisViolations"] = []
                node["metrics"]["staticAnalysisViolationsCount"] = 0

        # Update system-wide metrics
        if "systemMetrics" in graph_data:
            graph_data["systemMetrics"]["totalStaticAnalysisViolations"] = merged_count

        with open(graph_json_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2)

        print(f"[PMDIntegration] Merged {merged_count} PMD static analysis violations into {graph_json_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 static_analyzer.py <graph_json_path> <pmd_json_path>")
        sys.exit(1)
        
    g_path = sys.argv[1]
    pmd_path = sys.argv[2]
    
    integration = PMDIntegration()
    integration.merge_pmd_report(g_path, pmd_path)
