import os
import json
import networkx as nx
from itertools import islice

base_dir = "test_projects/github_benchmarks/java"
projects = [
    ("square_javapoet", "javapoet-1.12.0_graph.json", "javapoet-1.13.0_graph.json"),
    ("jhy_jsoup", "jsoup-1.14.1_graph.json", "jsoup-1.14.2_graph.json"),
    ("google_gson", "gson-parent-2.8.5_graph.json", "gson-parent-2.8.6_graph.json"),
    ("reactive-streams_reactive-streams-jvm", "v1.0.2_graph.json", "v1.0.3_graph.json"),
    ("krahets_hello-algo", "1.2.0_graph.json", "1.3.0_graph.json"),
    ("iluwatar_java-design-patterns", "open-source-java-design-patterns-1st-edition_graph.json", "open-source-java-design-patterns-2nd-edition_graph.json")
]

def load_graph(file_path):
    with open(file_path, 'r') as fh:
        data = json.load(fh)
    g = nx.DiGraph()
    for n in data.get("nodes", []):
        g.add_node(n["id"], name=n["name"], type=n["type"], metrics=n.get("metrics", {}))
    for e in data.get("edges", []):
        g.add_edge(e["source"], e["target"])
    return g

print("| Repository | Transition | LOC (v1) | LOC (v2) | Classes (v1) | Classes (v2) | Edges (v1) | Edges (v2) | Added Nodes | Del Nodes | Added Edges | Del Edges | New Cycles | Broken Cycles | Status |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

for folder, f1, f2 in projects:
    p1 = os.path.join(base_dir, folder, f1)
    p2 = os.path.join(base_dir, folder, f2)
    
    with open(p1) as fh1:
        d1 = json.load(fh1)
    with open(p2) as fh2:
        d2 = json.load(fh2)
        
    s1 = d1.get("systemMetrics", {})
    s2 = d2.get("systemMetrics", {})
    
    g1 = load_graph(p1)
    g2 = load_graph(p2)
    
    # Calculate cycles limited to 100
    cycles_g1 = list(islice(nx.simple_cycles(g1), 100))
    cycles_g2 = list(islice(nx.simple_cycles(g2), 100))
    
    new_cycles = [c for c in cycles_g2 if c not in cycles_g1]
    broken_cycles = [c for c in cycles_g1 if c not in cycles_g2]
    
    nodes1 = set(g1.nodes)
    nodes2 = set(g2.nodes)
    added_nodes = len(nodes2 - nodes1)
    del_nodes = len(nodes1 - nodes2)
    
    edges1 = set(g1.edges)
    edges2 = set(g2.edges)
    added_edges = len(edges2 - edges1)
    del_edges = len(edges1 - edges2)
    
    status = "Violation" if len(new_cycles) > 0 or added_nodes > 100 else "Satisfied"
    
    repo_name = folder.replace("_", "/")
    if repo_name == "reactive-streams/reactive-streams-jvm":
        repo_name = "reactive-streams"
        
    v1_name = f1.replace("_graph.json", "").replace("javapoet-", "").replace("jsoup-", "").replace("gson-parent-", "").replace("open-source-java-design-patterns-", "")
    v2_name = f2.replace("_graph.json", "").replace("javapoet-", "").replace("jsoup-", "").replace("gson-parent-", "").replace("open-source-java-design-patterns-", "")
    
    print(f"| `{repo_name}` | {v1_name} &rarr; {v2_name} | {s1.get('totalLinesOfCode')} | {s2.get('totalLinesOfCode')} | {s1.get('totalClasses')} | {s2.get('totalClasses')} | {len(edges1)} | {len(edges2)} | {added_nodes} | {del_nodes} | {added_edges} | {del_edges} | {len(new_cycles)} | {len(broken_cycles)} | **{status.upper()}** |")
