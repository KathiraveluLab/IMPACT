import os
import networkx as nx
from core.graph_utils import load_impact_graph

class GraphAgent:
    """Specialized agent for loading and querying software dependency graphs."""
    
    def __init__(self, name: str = "GraphAgent"):
        self.name = name

    def execute(self, file_path: str) -> dict:
        """Loads and returns summary statistics of the dependency graph."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Graph file not found: {file_path}")
            
        g = load_impact_graph(file_path)
        
        return {
            "version": g.graph["version"],
            "language": g.graph["language"],
            "node_count": len(g.nodes),
            "edge_count": len(g.edges),
            "system_metrics": g.graph["systemMetrics"]
        }
