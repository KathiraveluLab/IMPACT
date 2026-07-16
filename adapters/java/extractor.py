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
        start_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
                                # Fix 1: also collect qualified nested references (Outer.Inner)
                                if node.sub_type:
                                    references.add(f"{node.name}.{node.sub_type.name}")
                            elif isinstance(node, javalang.tree.MethodInvocation):
                                if node.qualifier:
                                    parts = node.qualifier.split('.')
                                    if parts:
                                        references.add(parts[0])
                                    # Collect qualified name for Outer.method() style calls
                                    if len(parts) == 2:
                                        references.add(node.qualifier)
                            elif isinstance(node, javalang.tree.MemberReference):
                                if node.qualifier:
                                    parts = node.qualifier.split('.')
                                    if parts:
                                        references.add(parts[0])
                        
                        imports = [imp.path for imp in tree.imports]
                        
                        parent_name = None
                        if hasattr(t, "extends") and t.extends:
                            if isinstance(t.extends, list):
                                if t.extends:
                                    parent_name = t.extends[0].name
                            elif hasattr(t.extends, "name"):
                                parent_name = t.extends.name

                        class_details[fqcn] = {
                            "name": class_name,
                            "package": package_name,
                            "filePath": os.path.relpath(filepath, src_dir),
                            "loc": loc,
                            "complexity": complexity,
                            "content": content,
                            "imports": imports,
                            "ast_references": list(references),
                            "use_ast": True,
                            "extends": parent_name
                        }
                        project_classes.add(fqcn)
                        class_name_to_fqcn.setdefault(class_name, set()).add(fqcn)

                        # Fix 2: register nested class declarations found inside class bodies
                        if hasattr(t, 'body') and t.body:
                            for member in t.body:
                                if isinstance(member, (
                                    javalang.tree.ClassDeclaration,
                                    javalang.tree.InterfaceDeclaration,
                                    javalang.tree.EnumDeclaration,
                                )):
                                    nested_name = member.name
                                    nested_fqcn = f"{fqcn}.{nested_name}"
                                    # Register as a graph node (inherits file/metrics from outer class)
                                    class_details[nested_fqcn] = {
                                        "name": nested_name,
                                        "package": package_name,
                                        "filePath": os.path.relpath(filepath, src_dir),
                                        "loc": 0,          # nested LOC not separately measured
                                        "complexity": 1,
                                        "content": "",
                                        "imports": imports,
                                        "ast_references": [],
                                        "use_ast": True
                                    }
                                    project_classes.add(nested_fqcn)
                                    class_name_to_fqcn.setdefault(nested_name, set()).add(nested_fqcn)
                                    # Register "OuterSimple.InnerSimple" for qualified lookup
                                    class_name_to_fqcn.setdefault(
                                        f"{class_name}.{nested_name}", set()
                                    ).add(nested_fqcn)


                    parsed_ast = True
                except Exception as e:
                    # AST parsing failed, log and fall back to regex
                    # (Can happen on new Java syntax elements like records or dynamic vars)
                    pass

            if not parsed_ast:
                # Regex Fallback with Java 17+ record / sealed class support
                package_match = re.search(r"package\s+([\w\.]+);", content)
                package_name = package_match.group(1) if package_match else ""
                imports = [imp.group(1) for imp in re.finditer(r"^import\s+([\w\.\*]+);", content, re.MULTILINE)]

                # 1. Look for Java 17+ record declarations
                record_matches = re.finditer(r"\brecord\s+(\w+)\s*\((.*?)\)", content)
                for rm in record_matches:
                    class_name = rm.group(1)
                    params = rm.group(2)
                    fqcn = f"{package_name}.{class_name}" if package_name else class_name
                    
                    # Extract dependencies from record parameters (e.g. Type param1)
                    references = set()
                    for param in params.split(","):
                        param = param.strip()
                        if param:
                            parts = param.split()
                            if len(parts) >= 2:
                                type_name = parts[-2]
                                type_name = re.sub(r"<.*?>", "", type_name) # clean generics
                                references.add(type_name)

                    class_details[fqcn] = {
                        "name": class_name,
                        "package": package_name,
                        "filePath": os.path.relpath(filepath, src_dir),
                        "loc": loc,
                        "complexity": complexity,
                        "content": content,
                        "imports": imports,
                        "ast_references": list(references),
                        "use_ast": False,
                        "extends": None
                    }
                    project_classes.add(fqcn)
                    class_name_to_fqcn.setdefault(class_name, set()).add(fqcn)

                # 2. Look for sealed/non-sealed class or interface declarations
                sealed_matches = re.finditer(r"\b(?:sealed\s+|non-sealed\s+)?(?:class|interface|enum)\s+(\w+)(?:\s+extends\s+([\w\.]+))?(?:\s+implements\s+([\w\.,\s]+))?(?:\s+permits\s+([\w\.,\s]+))?", content)
                for sm in sealed_matches:
                    class_name = sm.group(1)
                    if class_name == "record":
                        continue
                    extends_val = sm.group(2)
                    permits_val = sm.group(4)
                    
                    fqcn = f"{package_name}.{class_name}" if package_name else class_name
                    if fqcn in class_details:
                        continue # already registered (e.g., as a record)

                    references = set()
                    if permits_val:
                        for p in permits_val.split(","):
                            references.add(p.strip())

                    class_details[fqcn] = {
                        "name": class_name,
                        "package": package_name,
                        "filePath": os.path.relpath(filepath, src_dir),
                        "loc": loc,
                        "complexity": complexity,
                        "content": content,
                        "imports": imports,
                        "ast_references": list(references),
                        "use_ast": False,
                        "extends": extends_val
                    }
                    project_classes.add(fqcn)
                    class_name_to_fqcn.setdefault(class_name, set()).add(fqcn)

        # Compute inheritance depth for all classes
        inheritance_depths = {}
        def get_depth(fqcn_key, visited=None):
            if visited is None:
                visited = set()
            if fqcn_key in visited:
                return 0
            visited.add(fqcn_key)
            if fqcn_key in inheritance_depths:
                return inheritance_depths[fqcn_key]
            
            details = class_details.get(fqcn_key)
            if not details:
                return 0
            
            parent_name = details.get("extends")
            if not parent_name:
                inheritance_depths[fqcn_key] = 0
                return 0
            
            parent_fqcn = None
            # Check explicit imports
            for imp in details.get("imports", []):
                if imp.endswith(f".{parent_name}"):
                    if imp in project_classes:
                        parent_fqcn = imp
                        break
            
            # Check same package
            if not parent_fqcn:
                candidate = f"{details['package']}.{parent_name}" if details['package'] else parent_name
                if candidate in project_classes:
                    parent_fqcn = candidate
            
            # Check wildcard imports
            if not parent_fqcn:
                for imp in details.get("imports", []):
                    if imp.endswith(".*"):
                        candidate = f"{imp[:-2]}.{parent_name}"
                        if candidate in project_classes:
                            parent_fqcn = candidate
                            break
            
            # Global fallback
            if not parent_fqcn and parent_name in class_name_to_fqcn:
                candidates = class_name_to_fqcn[parent_name]
                if len(candidates) == 1:
                    parent_fqcn = list(candidates)[0]
            
            if parent_fqcn:
                d = 1 + get_depth(parent_fqcn, visited)
                inheritance_depths[fqcn_key] = d
                return d
            else:
                inheritance_depths[fqcn_key] = 1 # parent outside project
                return 1

        for f_key in class_details:
            get_depth(f_key)

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
                        continue

                    # Fix 3 / E. Resolve qualified nested references like "Outer.Inner"
                    if '.' in ref:
                        # E1. Direct lookup: "OuterSimple.InnerSimple" registered in first pass
                        if ref in class_name_to_fqcn:
                            candidates = class_name_to_fqcn[ref]
                            if len(candidates) == 1:
                                dependencies.add(list(candidates)[0])
                                continue
                        # E2. Resolve outer name -> FQCN, then append inner name
                        outer_ref, inner_name = ref.split('.', 1)
                        outer_fqcn = None
                        # Try explicit imports for the outer class
                        for imp in details["imports"]:
                            if imp.endswith(f".{outer_ref}"):
                                outer_fqcn = imp
                                break
                        # Try same-package outer class
                        if not outer_fqcn:
                            candidate = (
                                f"{details['package']}.{outer_ref}"
                                if details['package'] else outer_ref
                            )
                            if candidate in project_classes:
                                outer_fqcn = candidate
                        # Try wildcard imports for the outer class
                        if not outer_fqcn:
                            for imp in details["imports"]:
                                if imp.endswith(".*"):
                                    candidate = f"{imp[:-2]}.{outer_ref}"
                                    if candidate in project_classes:
                                        outer_fqcn = candidate
                                        break
                        if outer_fqcn:
                            nested_fqcn = f"{outer_fqcn}.{inner_name}"
                            if nested_fqcn in project_classes:
                                dependencies.add(nested_fqcn)
            else:
                # 2. Optimized Regex fallback: token-based set intersection with semantic resolution
                content = details["content"]
                tokens = set(re.findall(r"\b\w+\b", content))
                for simple_name in tokens:
                    if simple_name == details["name"]:
                        continue
                    if simple_name not in class_name_to_fqcn:
                        continue

                    resolved = False
                    # A. Check explicit imports
                    for imp in details["imports"]:
                        if imp.endswith(f".{simple_name}"):
                            target_fqcn = imp
                            if target_fqcn in project_classes:
                                dependencies.add(target_fqcn)
                                resolved = True
                                break
                    if resolved:
                        continue

                    # B. Check same package
                    target_fqcn = f"{details['package']}.{simple_name}" if details['package'] else simple_name
                    if target_fqcn in project_classes:
                        dependencies.add(target_fqcn)
                        continue

                    # C. Check wildcard imports
                    for imp in details["imports"]:
                        if imp.endswith(".*"):
                            wildcard_package = imp[:-2]
                            target_fqcn = f"{wildcard_package}.{simple_name}"
                            if target_fqcn in project_classes:
                                dependencies.add(target_fqcn)
                                resolved = True
                                break
                    if resolved:
                        continue

                    # D. Global fallback: Match simple name if unique in the project
                    candidates = class_name_to_fqcn[simple_name]
                    if len(candidates) == 1:
                        dependencies.add(list(candidates)[0])

            # Register resolved dependency edges (calls)
            for target_fqcn in dependencies:
                self.edges.append({
                    "source": fqcn,
                    "target": target_fqcn,
                    "type": "calls"
                })

            # Register inheritance edge if parent in project
            parent_name = details.get("extends")
            if parent_name:
                parent_fqcn = None
                # Check explicit imports
                for imp in details.get("imports", []):
                    if imp.endswith(f".{parent_name}"):
                        if imp in project_classes:
                            parent_fqcn = imp
                            break
                # Check same package
                if not parent_fqcn:
                    candidate = f"{details['package']}.{parent_name}" if details['package'] else parent_name
                    if candidate in project_classes:
                        parent_fqcn = candidate
                # Check wildcard imports
                if not parent_fqcn:
                    for imp in details.get("imports", []):
                        if imp.endswith(".*"):
                            candidate = f"{imp[:-2]}.{parent_name}"
                            if candidate in project_classes:
                                parent_fqcn = candidate
                                break
                # Global fallback
                if not parent_fqcn and parent_name in class_name_to_fqcn:
                    candidates = class_name_to_fqcn[parent_name]
                    if len(candidates) == 1:
                        parent_fqcn = list(candidates)[0]

                if parent_fqcn and parent_fqcn in project_classes:
                    self.edges.append({
                        "source": fqcn,
                        "target": parent_fqcn,
                        "type": "inheritance"
                    })

            # Register explicit import edges
            for imp in details.get("imports", []):
                if imp in project_classes and imp != fqcn:
                    # Avoid duplicates
                    exists = any(e["source"] == fqcn and e["target"] == imp and e["type"] in ("calls", "inheritance", "imports") for e in self.edges)
                    if not exists:
                        self.edges.append({
                            "source": fqcn,
                            "target": imp,
                            "type": "imports"
                        })

            self.nodes[fqcn] = {
                "id": fqcn,
                "name": details["name"],
                "type": "class",
                "filePath": details["filePath"],
                "metrics": {
                    "loc": details["loc"],
                    "complexity": details["complexity"],
                    "fanOut": 0,
                    "inheritanceDepth": inheritance_depths.get(fqcn, 0)
                }
            }

        # Update fanIn and fanOut metrics based on all edges
        for node in self.nodes.values():
            node["metrics"]["fanIn"] = 0
            node["metrics"]["fanOut"] = 0

        for edge in self.edges:
            source = edge["source"]
            target = edge["target"]
            if source in self.nodes:
                self.nodes[source]["metrics"]["fanOut"] += 1
            if target in self.nodes:
                self.nodes[target]["metrics"]["fanIn"] += 1

        # Fill default values and compute coupling
        for node in self.nodes.values():
            node["metrics"]["coupling"] = node["metrics"]["fanIn"] + node["metrics"]["fanOut"]

        # Calculate system-wide metrics
        total_loc = sum(n["metrics"]["loc"] for n in self.nodes.values())
        total_classes = len(self.nodes)
        avg_coupling = sum(n["metrics"]["coupling"] for n in self.nodes.values()) / max(1, total_classes)

        end_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        output_data = {
            "@context": {
                "@vocab": "https://w3id.org/impact/ontology#",
                "projectName": "projectName",
                "version": "versionString",
                "language": "language",
                "extractedAt": "extractedAt",
                "extractionStart": "extractionStart",
                "extractionEnd": "extractionEnd",
                "systemMetrics": "systemMetrics",
                "nodes": "hasEntity",
                "edges": "hasDependency",
                "id": "@id",
                "type": "@type",
                "source": {
                    "@id": "https://w3id.org/impact/ontology#source",
                    "@type": "@id"
                },
                "target": {
                    "@id": "https://w3id.org/impact/ontology#target",
                    "@type": "@id"
                },
                "class": "https://w3id.org/impact/ontology#ClassEntity",
                "interface": "https://w3id.org/impact/ontology#InterfaceEntity",
                "module": "https://w3id.org/impact/ontology#ModuleEntity",
                "package": "https://w3id.org/impact/ontology#ModuleEntity",
                "file": "https://w3id.org/impact/ontology#ModuleEntity",
                "function": "https://w3id.org/impact/ontology#FunctionEntity",
                "calls": "https://w3id.org/impact/ontology#Dependency",
                "inherits": "https://w3id.org/impact/ontology#Dependency",
                "inheritance": "https://w3id.org/impact/ontology#Dependency",
                "imports": "https://w3id.org/impact/ontology#Dependency",
                "implements": "https://w3id.org/impact/ontology#Dependency",
                "aggregates": "https://w3id.org/impact/ontology#Dependency",
                "depends_on": "https://w3id.org/impact/ontology#Dependency"
            },
            "projectName": self.project_name,
            "version": self.version,
            "language": "Java",
            "extractedAt": end_time,
            "extractionStart": start_time,
            "extractionEnd": end_time,
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

        # Write to .graph format (dual approach)
        if output_file.endswith(".json"):
            graph_file = output_file[:-5] + ".graph"
        else:
            graph_file = output_file + ".graph"
        try:
            import sys
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from core.graph_utils import export_graph_file
            export_graph_file(output_file, graph_file)
            print(f"[JavaExtractor] Exported human-readable graph to {graph_file}")
        except Exception as e:
            print(f"[JavaExtractor] Warning: Could not export .graph file: {e}")

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
