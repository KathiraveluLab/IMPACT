#!/usr/bin/env python3
"""
IMPACT Architectural Regression Testing Suite.
Verifies the end-to-end extraction, cycle detection, and SHACL schema validation logic.
"""

import os
import json
import unittest
import tempfile
import sys
from adapters.java.extractor import JavaExtractor
from core.shacl_validator import SHACLValidator

class TestArchitecturalRegression(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for test outputs
        self.test_dir = tempfile.TemporaryDirectory()
        self.output_json = os.path.join(self.test_dir.name, "extracted_graph.json")
        
        # Write dummy Java files inside a mock project directory
        self.src_dir = os.path.join(self.test_dir.name, "src")
        os.makedirs(self.src_dir, exist_ok=True)
        
        # Class A: base class
        with open(os.path.join(self.src_dir, "BaseService.java"), "w") as f:
            f.write("""
            package com.test;
            public class BaseService {
                public void init() {}
            }
            """)
            
        # Class B: inherits A and depends on C
        with open(os.path.join(self.src_dir, "MyService.java"), "w") as f:
            f.write("""
            package com.test;
            import com.test.BaseService;
            import com.test.HelperUtility;
            public class MyService extends BaseService {
                private HelperUtility helper = new HelperUtility();
                public void doWork() {
                    helper.calculate();
                }
            }
            """)
            
        # Class C: depends on B (introduces cycle)
        with open(os.path.join(self.src_dir, "HelperUtility.java"), "w") as f:
            f.write("""
            package com.test;
            import com.test.MyService;
            public class HelperUtility {
                private MyService service;
                public void calculate() {
                    if (service != null) {
                        service.init();
                    }
                }
            }
            """)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_end_to_end_regression(self):
        print("\n--- Running Architectural Regression Test ---")
        
        # 1. Run Java AST Extractor
        extractor = JavaExtractor("RegressionTestProject", "1.0.0")
        extractor.extract(self.src_dir, self.output_json)
        
        # Verify output JSON exists and is valid
        self.assertTrue(os.path.exists(self.output_json))
        with open(self.output_json, "r") as f:
            graph = json.load(f)
            
        # 2. Check entities
        self.assertEqual(graph["projectName"], "RegressionTestProject")
        self.assertEqual(graph["version"], "1.0.0")
        self.assertEqual(graph["language"], "Java")
        
        nodes = {n["id"]: n for n in graph["nodes"]}
        self.assertIn("com.test.BaseService", nodes)
        self.assertIn("com.test.MyService", nodes)
        self.assertIn("com.test.HelperUtility", nodes)
        
        # Check inheritance depth computed
        # BaseService has depth 0, MyService extends BaseService (depth 1)
        self.assertEqual(nodes["com.test.BaseService"]["metrics"]["inheritanceDepth"], 0)
        self.assertEqual(nodes["com.test.MyService"]["metrics"]["inheritanceDepth"], 1)
        
        # 3. Check edges
        edges = [(e["source"], e["target"], e["type"]) for e in graph["edges"]]
        self.assertIn(("com.test.MyService", "com.test.BaseService", "calls"), edges)
        self.assertIn(("com.test.MyService", "com.test.HelperUtility", "calls"), edges)
        self.assertIn(("com.test.HelperUtility", "com.test.MyService", "calls"), edges)
        
        # 4. Run SHACL schema validation
        validator = SHACLValidator()
        report = validator.validate_graph(self.output_json)
        is_compliant = report["conforms"]
        print(f"SHACL Compliance Result: {is_compliant}")
        self.assertTrue(is_compliant, f"SHACL Validation failed: {report['results']}")
        
        print("Regression testing suite completed successfully.")

if __name__ == "__main__":
    unittest.main()
