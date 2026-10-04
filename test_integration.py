import os
import shutil
import unittest
import subprocess
from pathlib import Path
from src.dependency_analyzer.ast_parser import DependencyParser
from src.dependency_analyzer.java_parser import JavaDependencyParser

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("data/test_mixed_repo")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Python file
        with open(self.test_dir / "math_utils.py", "w") as f:
            f.write("""def add(a, b):
    return a + b

class Calculator:
    def __init__(self):
        self.value = 0
    def multiply(self, a, b):
        return a * b
""")

        # Java file
        with open(self.test_dir / "StringUtil.java", "w") as f:
            f.write("""package com.example;

public class StringUtil {
    
    public StringUtil() {
    }
    
    public String concat(String a, String b) {
        return a + b;
    }
}
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_mixed_language_pipeline(self):
        # Run generate_docstrings.py in placeholder mode
        cmd = ["python", "generate_docstrings.py", "--repo-path", str(self.test_dir), "--test-mode", "placeholder"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Script failed with output: {result.stderr}\n{result.stdout}")
        
        # Verify Python insertion
        with open(self.test_dir / "math_utils.py", "r") as f:
            py_content = f.read()
            self.assertIn("Test docstring for function 'add'", py_content)
            self.assertIn("Test docstring for class 'Calculator'", py_content)
            self.assertIn("Test docstring for method 'multiply'", py_content)
            
        # Verify Java insertion
        with open(self.test_dir / "StringUtil.java", "r") as f:
            java_content = f.read()
            self.assertIn("/**\n * Test docstring for class 'StringUtil'.", java_content)
            self.assertIn("/**\n     * Test docstring for constructor 'StringUtil'.", java_content)
            self.assertIn("/**\n     * Test docstring for method 'concat_String_String' in class 'StringUtil'.", java_content)
            
        print("Integration test passed successfully!")

if __name__ == "__main__":
    unittest.main()
