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

    def test_nested_class_registration(self):
        """Nested class declarations inside a class body must be registered in project_classes."""
        os.makedirs(os.path.join(self.test_dir, "com", "example"), exist_ok=True)
        outer = """package com.example;
public class Container {
    public static class Item {
        private int value;
    }
    public static class Tag {}
}
"""
        with open(os.path.join(self.test_dir, "com", "example", "Container.java"), "w") as f:
            f.write(outer)

        extractor = JavaExtractor("NestedReg", "1.0")
        extractor.extract(self.test_dir, self.output_file)

        with open(self.output_file) as f:
            data = json.load(f)

        node_ids = {n["id"] for n in data["nodes"]}
        # Outer class is always registered
        self.assertIn("com.example.Container", node_ids)
        # Inner classes should now also appear via nested-type discovery
        self.assertIn("com.example.Container.Item", node_ids)
        self.assertIn("com.example.Container.Tag", node_ids)

    def test_nested_class_same_package_resolution(self):
        """A class referencing Outer.Inner in the same package resolves the edge correctly."""
        os.makedirs(os.path.join(self.test_dir, "com", "example"), exist_ok=True)
        container = """package com.example;
public class Container {
    public static class Item {
        public int id;
    }
}
"""
        consumer = """package com.example;
public class Consumer {
    private Container.Item item;
}
"""
        with open(os.path.join(self.test_dir, "com", "example", "Container.java"), "w") as f:
            f.write(container)
        with open(os.path.join(self.test_dir, "com", "example", "Consumer.java"), "w") as f:
            f.write(consumer)

        extractor = JavaExtractor("NestedSamePkg", "1.0")
        extractor.extract(self.test_dir, self.output_file)

        with open(self.output_file) as f:
            data = json.load(f)

        edges = data["edges"]
        # Consumer -> Container.Item edge must be resolved
        self.assertTrue(
            any(e["source"] == "com.example.Consumer" and e["target"] == "com.example.Container.Item"
                for e in edges),
            f"Expected Consumer->Container.Item edge. Got: {edges}"
        )

    def test_nested_class_explicit_import_resolution(self):
        """A class importing Outer.Inner explicitly resolves the dependency edge."""
        os.makedirs(os.path.join(self.test_dir, "com", "model"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "com", "service"), exist_ok=True)
        model = """package com.model;
public class Response {
    public static class Body {
        public String data;
    }
}
"""
        service = """package com.service;
import com.model.Response;
public class ApiService {
    private Response.Body body;
}
"""
        with open(os.path.join(self.test_dir, "com", "model", "Response.java"), "w") as f:
            f.write(model)
        with open(os.path.join(self.test_dir, "com", "service", "ApiService.java"), "w") as f:
            f.write(service)

        extractor = JavaExtractor("NestedImport", "1.0")
        extractor.extract(self.test_dir, self.output_file)

        with open(self.output_file) as f:
            data = json.load(f)

        node_ids = {n["id"] for n in data["nodes"]}
        self.assertIn("com.model.Response.Body", node_ids)

        edges = data["edges"]
        self.assertTrue(
            any(e["source"] == "com.service.ApiService" and e["target"] == "com.model.Response.Body"
                for e in edges),
            f"Expected ApiService->Response.Body edge. Got: {edges}"
        )

if __name__ == "__main__":
    unittest.main()
