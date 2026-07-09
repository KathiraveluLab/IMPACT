import os
import re
import json
from datetime import datetime, timezone

class JavaExtractor:
    """Java source code AST-like parser to extract IMPACT dependency graphs."""

    def __init__(self, project_name: str, version: str):
        self.project_name = project_name
        self.version = version
        self.nodes = {}
        self.edges = []

    def extract(self, src_dir: str, output_file: str):
        if not os.path.exists(src_dir):
            raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

        java_files = []
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(root, file))

        # First pass: find all classes/interfaces and their FQCNs
        class_details = {}
        for filepath in java_files:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract package name
            package_match = re.search(r"package\s+([\w\.]+);", content)
            package_name = package_match.group(1) if package_match else ""

            # Extract class/interface name
            class_match = re.search(r"public\s+(?:class|interface)\s+(\w+)", content)
            if not class_match:
                continue
            class_name = class_match.group(1)
            fqcn = f"{package_name}.{class_name}" if package_name else class_name

            # Calculate metrics
            lines = content.splitlines()
            loc = len([line for line in lines if line.strip() and not line.strip().startswith("//")])
            
            # Simple cyclomatic complexity approximation
            complexity = 1
            for line in lines:
                complexity += len(re.findall(r"\b(if|for|while|catch)\b|&&|\|\|", line))

            class_details[fqcn] = {
                "name": class_name,
                "filePath": os.path.relpath(filepath, src_dir),
                "loc": loc,
                "complexity": complexity,
                "content": content
            }

        # Second pass: detect dependencies
        for fqcn, details in class_details.items():
            content = details["content"]
            # Look for references to other classes in the project
            dependencies = []
            for other_fqcn, other_details in class_details.items():
                if fqcn == other_fqcn:
                    continue
                # Match simple class name as whole word (e.g. \bDatabase\b)
                pattern = rf"\b{other_details['name']}\b"
                if re.search(pattern, content):
                    dependencies.append(other_fqcn)
                    self.edges.append({
                        "source": fqcn,
                        "target": other_fqcn,
                        "type": "calls"
                    })

            self.nodes[fqcn] = {
                "id": fqcn,
                "name": details["name"],
                "type": "class",
                "filePath": details["filePath"],
                "metrics": {
                    "loc": details["loc"],
                    "complexity": details["complexity"],
                    "fanOut": len(dependencies)
                }
            }

        # Update fanIn metrics
        for edge in self.edges:
            target = edge["target"]
            if target in self.nodes:
                self.nodes[target]["metrics"]["fanIn"] = self.nodes[target]["metrics"].get("fanIn", 0) + 1

        # Fill default values for fanIn/fanOut
        for node in self.nodes.values():
            if "fanIn" not in node["metrics"]:
                node["metrics"]["fanIn"] = 0
            # Calculate simple coupling metric
            node["metrics"]["coupling"] = node["metrics"]["fanIn"] + node["metrics"]["fanOut"]

        # Calculate system-wide metrics
        total_loc = sum(n["metrics"]["loc"] for n in self.nodes.values())
        total_classes = len(self.nodes)
        avg_coupling = sum(n["metrics"]["coupling"] for n in self.nodes.values()) / max(1, total_classes)

        output_data = {
            "@context": {
                "@vocab": "https://w3id.org/impact/ontology#",
                "projectName": "projectName",
                "version": "versionString",
                "language": "language",
                "extractedAt": "extractedAt",
                "systemMetrics": "systemMetrics",
                "nodes": "hasEntity",
                "edges": "hasDependency",
                "id": "@id",
                "type": "@type",
                "source": "source",
                "target": "target"
            },
            "projectName": self.project_name,
            "version": self.version,
            "language": "Java",
            "extractedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "systemMetrics": {
                "totalLinesOfCode": total_loc,
                "totalClasses": total_classes,
                "averageCoupling": avg_coupling
            },
            "nodes": list(self.nodes.values()),
            "edges": self.edges
        }


        # Write to JSON
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

        print(f"[JavaExtractor] Extracted graph for {self.project_name} v{self.version} to {output_file}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 5:
        print("Usage: python3 extractor.py <project_name> <version> <src_dir> <output_file>")
        sys.exit(1)
    
    p_name = sys.argv[1]
    ver = sys.argv[2]
    s_dir = sys.argv[3]
    out_f = sys.argv[4]
    
    extractor = JavaExtractor(p_name, ver)
    extractor.extract(s_dir, out_f)
