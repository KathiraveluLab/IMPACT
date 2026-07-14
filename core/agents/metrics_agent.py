import os
import networkx as nx
from core.graph_utils import load_impact_graph

class MetricsAgent:
    """Specialized agent for calculating network and architecture metrics (e.g., centrality, coupling, anomalies)."""
    
    def __init__(self, name: str = "MetricsAgent"):
        self.name = name

    def execute(self, file_path: str) -> dict:
        """Calculates advanced metrics and performs coupling anomaly detection on a dependency graph."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Graph file not found: {file_path}")
            
        g = load_impact_graph(file_path)
        
        # Calculate network centralities
        degree_centrality = nx.degree_centrality(g)
        
        # Identify highly coupled hub components (top 3)
        hubs = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Perform anomaly detection on class coupling values
        coupling_values = {}
        for node_id in g.nodes:
            node_data = g.nodes[node_id]
            coupling = node_data.get("metrics", {}).get("coupling")
            if coupling is None:
                coupling = g.in_degree(node_id) + g.out_degree(node_id)
            coupling_values[node_id] = coupling
            
        vals = list(coupling_values.values())
        anomalies = []
        if len(vals) > 0:
            mean = sum(vals) / len(vals)
            variance = sum((x - mean) ** 2 for x in vals) / len(vals)
            std_dev = variance ** 0.5
            threshold = mean + 2 * std_dev
            # Minimum threshold of 3.0 to prevent flagging tiny values on small codebases
            threshold = max(3.0, threshold)
            
            for n_id, val in coupling_values.items():
                if val > threshold:
                    z_score = (val - mean) / max(0.1, std_dev)
                    anomalies.append({
                        "id": n_id,
                        "coupling": val,
                        "z_score": round(z_score, 2)
                    })
        
        return {
            "version": g.graph["version"],
            "degree_centrality": degree_centrality,
            "top_hubs": [{"id": h[0], "centrality": h[1]} for h in hubs],
            "coupling_anomalies": anomalies
        }
