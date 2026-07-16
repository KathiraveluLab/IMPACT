import unittest
import os
import networkx as nx
from unittest.mock import patch
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

    def test_shacl_validator(self):
        from core.shacl_validator import SHACLValidator
        validator = SHACLValidator()
        report1 = validator.validate_graph(self.file_v1)
        report2 = validator.validate_graph(self.file_v2)
        self.assertTrue(report1["conforms"])
        self.assertTrue(report2["conforms"])

        # Test invalid graph validation
        import tempfile
        import json
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tmp:
            invalid_data = {
                "projectName": "InvalidProject",
                "version": "1.0",
                "language": "Java",
                "nodes": [
                    {
                        "id": "com.invalid.ClassA",
                        "name": "ClassA",
                        "type": "class",
                        "metrics": {
                            # missing loc
                            "complexity": 1,
                            "inheritanceDepth": 0
                        }
                    }
                ],
                "edges": [
                    {
                        "source": "com.invalid.ClassA",
                        "target": "com.invalid.NonExistent",
                        "type": "calls"
                    }
                ]
            }
            json.dump(invalid_data, tmp)
            tmp_path = tmp.name

        try:
            report_invalid = validator.validate_graph(tmp_path)
            self.assertFalse(report_invalid["conforms"])
            self.assertTrue(len(report_invalid["results"]) > 0)
            
            results_text = " ".join(report_invalid["results"])
            self.assertTrue("loc" in results_text or "SoftwareEntity" in results_text or "constraint" in results_text)
        finally:
            import os
            os.remove(tmp_path)

    @patch("sqlite3.connect")
    @patch("core.ecosystem_crawler.GitHubEcosystemCrawler")
    @patch("os.path.exists")
    @patch("builtins.open")
    def test_ecosystem_coordinator(self, mock_open, mock_exists, mock_crawler_class, mock_connect):
        from unittest.mock import MagicMock, patch
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.side_effect = [
            (1, "crawled", "1.0.0", "2.0.0"),
            ("crawled", "1.0.0", "2.0.0", None)
        ]
        
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.read.return_value = "Swarm Analysis Report: Intent Satisfied"
        mock_open.return_value.__enter__.return_value = mock_file

        coordinator = CoordinatorAgent()
        report = coordinator.run_ecosystem_analysis("owner/repo", ["avoid cyclic dependencies"])
        
        self.assertEqual(report, "Swarm Analysis Report: Intent Satisfied")
        mock_crawler_class.assert_called_once()

if __name__ == "__main__":
    unittest.main()

