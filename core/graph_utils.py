import json
import networkx as nx

def load_impact_graph(file_path: str) -> nx.DiGraph:
    """Loads a standardized IMPACT graph JSON file into a NetworkX DiGraph."""
    with open(file_path, 'r') as f:
        data = json.load(f)
        
    g = nx.DiGraph(
        projectName=data["projectName"],
        version=data["version"],
        language=data["language"],
        systemMetrics=data.get("systemMetrics", {})
    )
    
    for node in data["nodes"]:
        g.add_node(
            node["id"],
            name=node["name"],
            type=node["type"],
            filePath=node.get("filePath", ""),
            metrics=node.get("metrics", {})
        )
        
    for edge in data["edges"]:
        g.add_edge(
            edge["source"],
            edge["target"],
            type=edge["type"]
        )
        
    return g

def compare_graphs(g1: nx.DiGraph, g2: nx.DiGraph) -> dict:
    """Compares two versions of a dependency graph and returns structural changes."""
    added_nodes = [n for n in g2.nodes if n not in g1.nodes]
    removed_nodes = [n for n in g1.nodes if n not in g2.nodes]
    
    added_edges = [e for e in g2.edges if e not in g1.edges]
    removed_edges = [e for e in g1.edges if e not in g2.edges]
    
    from itertools import islice
    # Analyze dependency cycles (limit to 100 to prevent hanging on large codebases)
    cycles_g1 = list(islice(nx.simple_cycles(g1), 100))
    cycles_g2 = list(islice(nx.simple_cycles(g2), 100))
    
    new_cycles = [c for c in cycles_g2 if c not in cycles_g1]
    broken_cycles = [c for c in cycles_g1 if c not in cycles_g2]
    
    return {
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "new_cycles": new_cycles,
        "broken_cycles": broken_cycles
    }

def export_graph_file(json_path: str, graph_path: str):
    """Exports nodes and edges from a standardized IMPACT JSON graph to a human-readable .graph file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    with open(graph_path, 'w', encoding='utf-8') as f:
        f.write(f"# Project: {data.get('projectName')}\n")
        f.write(f"# Version: {data.get('version')}\n")
        f.write(f"# Language: {data.get('language')}\n")
        f.write("\n# Nodes: classes and modules\n")
        
        # Write nodes
        for node in data.get("nodes", []):
            node_id = node.get("id")
            node_type = node.get("type", "class")
            f.write(f"node: {node_id} [{node_type}]\n")
            
        f.write("\n# Edges: dependencies (calls, inheritance, imports)\n")
        
        # Write edges
        for edge in data.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            edge_type = edge.get("type", "calls")
            f.write(f"edge: {source} -> {target} [{edge_type}]\n")

