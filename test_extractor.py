import unittest
import os
import shutil
import tempfile
import json
from adapters.java.extractor import JavaExtractor

class TestJavaExtractor(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.test_dir, "graph.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_ast_extraction(self):
        """Verify that AST dependency parsing extracts nodes and reference edges correctly."""
        os.makedirs(os.path.join(self.test_dir, "com", "example"), exist_ok=True)
        
        class_a = """package com.example;
import com.example.ClassB;
public class ClassA {
    private ClassB b;
    public void doWork() {
        b.perform();
    }
}
"""
        class_b = """package com.example;
public class ClassB {
    public void perform() {}
}
"""
        with open(os.path.join(self.test_dir, "com", "example", "ClassA.java"), "w") as f:
            f.write(class_a)
        with open(os.path.join(self.test_dir, "com", "example", "ClassB.java"), "w") as f:
            f.write(class_b)

        extractor = JavaExtractor("TestProject", "1.0")
        extractor.extract(self.test_dir, self.output_file)

        self.assertTrue(os.path.exists(self.output_file))
        with open(self.output_file, "r") as f:
            data = json.load(f)

        self.assertEqual(data["projectName"], "TestProject")
        self.assertEqual(data["version"], "1.0")
        
        nodes = {n["id"]: n for n in data["nodes"]}
        self.assertIn("com.example.ClassA", nodes)
        self.assertIn("com.example.ClassB", nodes)
        
        edges = data["edges"]
        self.assertTrue(any(e["source"] == "com.example.ClassA" and e["target"] == "com.example.ClassB" for e in edges))

    def test_regex_fallback_non_public_classes(self):
        """Verify that the regex fallback parser successfully processes non-public classes."""
        import adapters.java.extractor
        original_has_javalang = adapters.java.extractor.HAS_JAVALANG
        adapters.java.extractor.HAS_JAVALANG = False

        try:
            os.makedirs(os.path.join(self.test_dir, "com", "example"), exist_ok=True)
            
            class_a = """package com.example;
class ClassA {
    ClassB b;
}
"""
            class_b = """package com.example;
abstract class ClassB {
    ClassC c;
}
"""
            class_c = """package com.example;
final class ClassC {}
"""
            with open(os.path.join(self.test_dir, "com", "example", "ClassA.java"), "w") as f:
                f.write(class_a)
            with open(os.path.join(self.test_dir, "com", "example", "ClassB.java"), "w") as f:
                f.write(class_b)
            with open(os.path.join(self.test_dir, "com", "example", "ClassC.java"), "w") as f:
                f.write(class_c)

            extractor = JavaExtractor("TestFallback", "1.0")
            extractor.extract(self.test_dir, self.output_file)

            self.assertTrue(os.path.exists(self.output_file))
            with open(self.output_file, "r") as f:
                data = json.load(f)

            nodes = {n["id"]: n for n in data["nodes"]}
            self.assertIn("com.example.ClassA", nodes)
            self.assertIn("com.example.ClassB", nodes)
            self.assertIn("com.example.ClassC", nodes)

            edges = data["edges"]
            self.assertTrue(any(e["source"] == "com.example.ClassA" and e["target"] == "com.example.ClassB" for e in edges))
            self.assertTrue(any(e["source"] == "com.example.ClassB" and e["target"] == "com.example.ClassC" for e in edges))

        finally:
            adapters.java.extractor.HAS_JAVALANG = original_has_javalang

if __name__ == "__main__":
    unittest.main()
