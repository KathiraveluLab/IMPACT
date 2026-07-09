import os
import networkx as nx
from core.graph_utils import load_impact_graph

class MetricsAgent:
    """Specialized agent for calculating network and architecture metrics (e.g., centrality, coupling)."""
    
    def __init__(self, name: str = "MetricsAgent"):
        self.name = name

    def execute(self, file_path: str) -> dict:
        """Calculates advanced metrics on a dependency graph."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Graph file not found: {file_path}")
            
        g = load_impact_graph(file_path)
        
        # Calculate network centralities
        degree_centrality = nx.degree_centrality(g)
        
        # Identify highly coupled hub components (top 3)
        hubs = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "version": g.graph["version"],
            "degree_centrality": degree_centrality,
            "top_hubs": [{"id": h[0], "centrality": h[1]} for h in hubs]
        }
