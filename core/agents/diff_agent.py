import os
from core.graph_utils import load_impact_graph, compare_graphs

class DiffAgent:
    """Specialized agent for detecting structural differences and cycle shifts between versions."""
    
    def __init__(self, name: str = "DiffAgent"):
        self.name = name

    def execute(self, file_path_v1: str, file_path_v2: str) -> dict:
        """Compares two versions of a dependency graph and returns the diff report."""
        if not os.path.exists(file_path_v1) or not os.path.exists(file_path_v2):
            raise FileNotFoundError("One or both graph files were not found.")
            
        g1 = load_impact_graph(file_path_v1)
        g2 = load_impact_graph(file_path_v2)
        
        diff = compare_graphs(g1, g2)
        
        return {
            "version_old": g1.graph["version"],
            "version_new": g2.graph["version"],
            "added_nodes_count": len(diff["added_nodes"]),
            "removed_nodes_count": len(diff["removed_nodes"]),
            "added_edges_count": len(diff["added_edges"]),
            "removed_edges_count": len(diff["removed_edges"]),
            "new_cycles_count": len(diff["new_cycles"]),
            "broken_cycles_count": len(diff["broken_cycles"]),
            "raw_diff": diff
        }
