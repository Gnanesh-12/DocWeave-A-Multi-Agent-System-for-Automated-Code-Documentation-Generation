import os
import shutil
import unittest
from pathlib import Path
from src.dependency_analyzer.java_parser import JavaDependencyParser
from src.dependency_analyzer.java_inserter import JavaInserter

class TestJavaInserter(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("data/test_java_inserter")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.java_file = self.test_dir / "TestFile.java"
        with open(self.java_file, "w") as f:
            f.write("""package com.example;

import java.util.List;

public class TestFile {
    
    private int field;

    public TestFile() {
    }

    @Override
    public void myMethod() {
    }
    
    public class Nested {
        public void nestedMethod() {}
    }
}
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_insert_javadocs(self):
        parser = JavaDependencyParser(str(self.test_dir))
        components = parser.parse_repository()
        
        c_class = components["com.example.TestFile"]
        c_constructor = components["com.example.TestFile.TestFile"]
        c_method = components["com.example.TestFile.myMethod"]
        c_nested_class = components["com.example.TestFile.Nested"]
        c_nested_method = components["com.example.TestFile.Nested.nestedMethod"]
        
        inserter = JavaInserter()
        
        insertions = [
            (c_class, "Class doc"),
            (c_constructor, "Constructor doc"),
            (c_method, "Method doc\n@return void"),
            (c_nested_class, "Nested class doc"),
            (c_nested_method, "Nested method doc")
        ]
        
        success = inserter.insert_javadocs(str(self.java_file), insertions)
        self.assertTrue(success)
        
        with open(self.java_file, "r") as f:
            content = f.read()
            
        # Check formatting and locations
        self.assertIn("/**\n * Class doc\n */\npublic class TestFile", content)
        self.assertIn("    /**\n     * Constructor doc\n     */\n    public TestFile()", content)
        self.assertIn("    /**\n     * Method doc\n     * @return void\n     */\n    @Override\n    public void myMethod()", content)
        self.assertIn("    /**\n     * Nested class doc\n     */\n    public class Nested", content)
        self.assertIn("        /**\n         * Nested method doc\n         */\n        public void nestedMethod()", content)

    def test_duplicate_avoidance(self):
        # File with existing javadoc
        file_path = self.test_dir / "Existing.java"
        with open(file_path, "w") as f:
            f.write("""package com.example;
/**
 * Existing doc.
 */
public class Existing {
}
""")
        parser = JavaDependencyParser(str(self.test_dir))
        components = parser.parse_repository()
        c_class = components["com.example.Existing"]
        
        self.assertTrue(c_class.has_docstring)
        
        inserter = JavaInserter()
        success = inserter.insert_javadocs(str(file_path), [(c_class, "New doc")])
        self.assertTrue(success) # Should succeed but do nothing
        
        with open(file_path, "r") as f:
            content = f.read()
            self.assertIn("Existing doc.", content)
            self.assertNotIn("New doc", content)

if __name__ == "__main__":
    unittest.main()
