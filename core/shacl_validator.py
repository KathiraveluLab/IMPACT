import json
import os
import rdflib
from pyshacl import validate

class SHACLValidator:
    """Validator that checks IMPACT graphs against structural SHACL constraints using W3C SHACL."""

    def validate_graph(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Graph file not found: {file_path}")

        # Resolve ontology and shapes paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        shapes_path = os.path.join(base_dir, "schema", "shapes.ttl")
        ontology_path = os.path.join(base_dir, "schema", "impact.ttl")

        if not os.path.exists(shapes_path):
            raise FileNotFoundError(f"SHACL shapes file not found: {shapes_path}")
        if not os.path.exists(ontology_path):
            raise FileNotFoundError(f"Ontology file not found: {ontology_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Ensure JSON-LD context has proper type mappings and coercion
            ctx = data.setdefault("@context", {})
            ctx.update({
                "@vocab": "https://w3id.org/impact/ontology#",
                "id": "@id",
                "type": "@type",
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
                "depends_on": "https://w3id.org/impact/ontology#Dependency",
                "source": {
                    "@id": "https://w3id.org/impact/ontology#source",
                    "@type": "@id"
                },
                "target": {
                    "@id": "https://w3id.org/impact/ontology#target",
                    "@type": "@id"
                }
            })

            # Load the data graph
            data_graph = rdflib.Graph()
            data_graph.parse(data=json.dumps(data), format="json-ld")

            # Flatten metrics properties directly onto the entity subject node
            # so they match the ontology domains and SHACL shapes
            metrics_uri = rdflib.URIRef("https://w3id.org/impact/ontology#metrics")
            for s, p, o in data_graph.triples((None, metrics_uri, None)):
                for ms, mp, mo in data_graph.triples((o, None, None)):
                    data_graph.add((s, mp, mo))

            # Load shapes and ontology
            shapes_graph = rdflib.Graph()
            shapes_graph.parse(shapes_path, format="turtle")

            ont_graph = rdflib.Graph()
            ont_graph.parse(ontology_path, format="turtle")

            # Validate using W3C SHACL engine (pyshacl)
            conforms, results_graph, results_text = validate(
                data_graph,
                shacl_graph=shapes_graph,
                ont_graph=ont_graph,
                inference='rdfs',
                serialize_report_graph=False
            )

            # Extract detailed violations from the validation results graph
            results = []
            if not conforms:
                sh = rdflib.Namespace("http://www.w3.org/ns/shacl#")
                for result_uri in results_graph.subjects(rdflib.RDF.type, sh.ValidationResult):
                    focus_node = next(results_graph.objects(result_uri, sh.focusNode), None)
                    path = next(results_graph.objects(result_uri, sh.resultPath), None)
                    msg = next(results_graph.objects(result_uri, sh.resultMessage), None)
                    
                    node_name = str(focus_node).split("/")[-1] if focus_node else "Unknown"
                    prop_name = str(path).split("#")[-1] if path else ""
                    
                    if msg:
                        msg_str = str(msg)
                    else:
                        msg_str = f"Violation [{node_name}]: Failed constraint check on path '{prop_name}'"
                    results.append(msg_str)

            return {
                "conforms": conforms,
                "results": results
            }

        except Exception as e:
            return {
                "conforms": False,
                "results": [f"SHACL validation error: {e}"]
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
