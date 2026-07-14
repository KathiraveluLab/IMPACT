import json
import os

class SHACLValidator:
    """Validator that checks IMPACT graphs against structural SHACL constraints."""

    def validate_graph(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Graph file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        conforms = True
        results = []

        # Validate nodes against ClassEntityShape
        node_ids = set()
        for node in data.get("nodes", []):
            n_id = node.get("id")
            if not n_id:
                conforms = False
                results.append("Violation: Node is missing a unique ID.")
                continue
            
            node_ids.add(n_id)
            metrics = node.get("metrics", {})

            # Check sh:path impact:loc
            if "loc" not in metrics:
                conforms = False
                results.append(f"Violation [{n_id}]: ClassEntity is missing a Lines of Code (loc) metric.")

            # Check sh:path impact:complexity
            if "complexity" not in metrics:
                conforms = False
                results.append(f"Violation [{n_id}]: ClassEntity is missing a cyclomatic complexity metric.")

            # Check sh:path impact:inheritanceDepth
            if "inheritanceDepth" not in metrics:
                conforms = False
                results.append(f"Violation [{n_id}]: ClassEntity is missing an inheritance depth metric.")

        # Validate edges against DependencyShape
        for edge in data.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")

            if not source or source not in node_ids:
                conforms = False
                results.append(f"Violation: Edge has invalid or missing source node ID: '{source}'.")

            if not target or target not in node_ids:
                conforms = False
                results.append(f"Violation: Edge has invalid or missing target node ID: '{target}'.")

        return {
            "conforms": conforms,
            "results": results
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 shacl_validator.py <graph_json_path>")
        sys.exit(1)
        
    g_path = sys.argv[1]
    validator = SHACLValidator()
    report = validator.validate_graph(g_path)
    
    print(f"SHACL Validation Report for: {g_path}")
    print(f"Conforms: {report['conforms']}")
    if report["results"]:
        print("Violations:")
        for r in report["results"]:
            print(f"- {r}")
    else:
        print("All structural constraints successfully satisfied.")
