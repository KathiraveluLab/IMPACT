import os
import re
import json
from datetime import datetime, timezone

try:
    import javalang
    HAS_JAVALANG = True
except ImportError:
    HAS_JAVALANG = False

class JavaExtractor:
    """Java source code AST-like parser to extract IMPACT dependency graphs using AST and regex fallbacks."""

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
        project_classes = set() # Set of all FQCNs in the project
        class_name_to_fqcn = {} # Map simple name -> set of FQCNs for resolving references

        for filepath in java_files:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Calculate LOC and complexity metrics (consistent across both parsing modes)
            lines = content.splitlines()
            loc = len([line for line in lines if line.strip() and not line.strip().startswith("//")])
            complexity = 1
            for line in lines:
                complexity += len(re.findall(r"\b(if|for|while|catch)\b|&&|\|\|", line))

            parsed_ast = False
            if HAS_JAVALANG:
                try:
                    tree = javalang.parse.parse(content)
                    package_name = tree.package.name if tree.package else ""
                    
                    for t in tree.types:
                        class_name = t.name
                        fqcn = f"{package_name}.{class_name}" if package_name else class_name
                        
                        # Collect references from AST
                        references = set()
                        for path, node in tree:
                            if isinstance(node, javalang.tree.ReferenceType):
                                references.add(node.name)
                            elif isinstance(node, javalang.tree.MethodInvocation):
                                if node.qualifier:
                                    parts = node.qualifier.split('.')
                                    if parts:
                                        references.add(parts[0])
                            elif isinstance(node, javalang.tree.MemberReference):
                                if node.qualifier:
                                    parts = node.qualifier.split('.')
                                    if parts:
                                        references.add(parts[0])
                        
                        imports = [imp.path for imp in tree.imports]
                        
                        class_details[fqcn] = {
                            "name": class_name,
                            "package": package_name,
                            "filePath": os.path.relpath(filepath, src_dir),
                            "loc": loc,
                            "complexity": complexity,
                            "content": content,
                            "imports": imports,
                            "ast_references": list(references),
                            "use_ast": True
                        }
                        project_classes.add(fqcn)
                        class_name_to_fqcn.setdefault(class_name, set()).add(fqcn)
                    
                    parsed_ast = True
                except Exception as e:
                    # AST parsing failed, log and fall back to regex
                    # (Can happen on new Java syntax elements like records or dynamic vars)
                    pass

            if not parsed_ast:
                # Regex Fallback
                package_match = re.search(r"package\s+([\w\.]+);", content)
                package_name = package_match.group(1) if package_match else ""

                class_match = re.search(r"public\s+(?:class|interface)\s+(\w+)", content)
                if not class_match:
                    continue
                class_name = class_match.group(1)
                fqcn = f"{package_name}.{class_name}" if package_name else class_name

                class_details[fqcn] = {
                    "name": class_name,
                    "package": package_name,
                    "filePath": os.path.relpath(filepath, src_dir),
                    "loc": loc,
                    "complexity": complexity,
                    "content": content,
                    "use_ast": False
                }
                project_classes.add(fqcn)
                class_name_to_fqcn.setdefault(class_name, set()).add(fqcn)

        # Second pass: resolve dependencies
        for fqcn, details in class_details.items():
            dependencies = set()
            
            if details.get("use_ast"):
                # 1. Resolve AST-collected references semantically
                for ref in details["ast_references"]:
                    if ref == details["name"]:
                        continue # Skip self-references
                    
                    resolved = False
                    
                    # A. Check explicit imports (e.g. import com.example.service.DbService;)
                    for imp in details["imports"]:
                        if imp.endswith(f".{ref}"):
                            target_fqcn = imp
                            if target_fqcn in project_classes:
                                dependencies.add(target_fqcn)
                                resolved = True
                                break
                    if resolved:
                        continue
                        
                    # B. Check same package (e.g. current_package.DbService)
                    target_fqcn = f"{details['package']}.{ref}" if details['package'] else ref
                    if target_fqcn in project_classes:
                        dependencies.add(target_fqcn)
                        continue
                        
                    # C. Check wildcard imports (e.g. import com.example.service.*;)
                    for imp in details["imports"]:
                        if imp.endswith(".*"):
                            wildcard_package = imp[:-2]
                            target_fqcn = f"{wildcard_package}.{ref}"
                            if target_fqcn in project_classes:
                                dependencies.add(target_fqcn)
                                resolved = True
                                break
                    if resolved:
                        continue
                        
                    # D. Global fallback: Match simple name if unique in the project
                    if ref in class_name_to_fqcn:
                        candidates = class_name_to_fqcn[ref]
                        if len(candidates) == 1:
                            dependencies.add(list(candidates)[0])
            else:
                # 2. Regex fallback: search simple class name matches in the text content
                content = details["content"]
                for other_fqcn, other_details in class_details.items():
                    if fqcn == other_fqcn:
                        continue
                    pattern = rf"\b{other_details['name']}\b"
                    if re.search(pattern, content):
                        dependencies.add(other_fqcn)

            # Register resolved dependency edges
            for target_fqcn in dependencies:
                self.edges.append({
                    "source": fqcn,
                    "target": target_fqcn,
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

        print(f"[JavaExtractor] Extracted graph via {'AST' if HAS_JAVALANG else 'Regex'} for {self.project_name} v{self.version} to {output_file}")

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
