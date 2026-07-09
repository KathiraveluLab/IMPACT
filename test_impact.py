import unittest
import os
import networkx as nx
from core.graph_utils import load_impact_graph, compare_graphs
from core.agents.coordinator import CoordinatorAgent

class TestImpactSwarm(unittest.TestCase):
    
    def setUp(self):
        self.file_v1 = "test_projects/v1_graph.json"
        self.file_v2 = "test_projects/v2_graph.json"
        
    def test_load_graph(self):
        g = load_impact_graph(self.file_v1)
        self.assertEqual(g.graph["projectName"], "TelemetryService")
        self.assertEqual(g.graph["version"], "1.0.0")
        self.assertEqual(len(g.nodes), 3)
        self.assertEqual(len(g.edges), 2)
        
    def test_compare_graphs(self):
        g1 = load_impact_graph(self.file_v1)
        g2 = load_impact_graph(self.file_v2)
        diff = compare_graphs(g1, g2)
        self.assertIn("com.telemetry.NewUtility", diff["added_nodes"])
        self.assertEqual(len(diff["new_cycles"]), 1)
        
    def test_coordinator(self):
        coordinator = CoordinatorAgent()
        report = coordinator.run_analysis(
            self.file_v1, 
            self.file_v2, 
            ["avoid cyclic dependencies"]
        )
        self.assertIn("VIOLATION", report)
        self.assertIn("new cyclic dependencies detected", report.lower())

if __name__ == "__main__":
    unittest.main()
