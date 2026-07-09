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
    
    # Analyze dependency cycles
    cycles_g1 = list(nx.simple_cycles(g1))
    cycles_g2 = list(nx.simple_cycles(g2))
    
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
