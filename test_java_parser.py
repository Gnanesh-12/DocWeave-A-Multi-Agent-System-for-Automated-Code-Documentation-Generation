import os
import shutil
import unittest
from pathlib import Path
from src.dependency_analyzer.java_parser import JavaDependencyParser
from src.dependency_analyzer.topo_sort import build_graph_from_components, dependency_first_dfs

class TestJavaParser(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("data/test_java_repo")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # File 1: Base interface
        with open(self.test_dir / "MyInterface.java", "w") as f:
            f.write("""package com.example;
public interface MyInterface {
    void doSomething();
}
""")
        
        # File 2: Class A and B with circular dependencies
        with open(self.test_dir / "ClassA.java", "w") as f:
            f.write("""package com.example;
public class ClassA {
    public ClassB b;
}
""")
        with open(self.test_dir / "ClassB.java", "w") as f:
            f.write("""package com.example;
public class ClassB {
    public ClassA a;
}
""")

        # File 3: Main class with references and overloaded methods
        with open(self.test_dir / "MyClass.java", "w") as f:
            f.write("""package com.example;
import java.util.List;
import com.example.model.Student;

/**
 * This is MyClass.
 */
public class MyClass implements MyInterface {
    
    public MyClass() {
    }
    
    /**
     * My method.
     */
    public int myMethod(int a, String b) {
        Student s = new Student();
        this.helperMethod();
        return a;
    }
    
    public int myMethod(String c) {
        return 0;
    }
    
    public void helperMethod() {
        // do something
    }
}
""")

        # File 4: Student class in subpackage
        model_dir = self.test_dir / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        with open(model_dir / "Student.java", "w") as f:
            f.write("""package com.example.model;
public class Student {
}
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parser_and_graph(self):
        parser = JavaDependencyParser(str(self.test_dir))
        components = parser.parse_repository()
        
        # Check components were extracted with correct overloaded IDs
        self.assertIn("com.example.MyInterface", components)
        self.assertIn("com.example.ClassA", components)
        self.assertIn("com.example.ClassB", components)
        self.assertIn("com.example.MyClass", components)
        self.assertIn("com.example.MyClass.MyClass", components) # Constructor
        self.assertIn("com.example.MyClass.myMethod_int_String", components)
        self.assertIn("com.example.MyClass.myMethod_String", components)
        self.assertIn("com.example.MyClass.helperMethod", components)
        self.assertIn("com.example.model.Student", components)
        
        my_method_int = components["com.example.MyClass.myMethod_int_String"]
        my_method_str = components["com.example.MyClass.myMethod_String"]
        
        # Ensure self-dependencies are removed
        self.assertNotIn("com.example.MyClass.myMethod_int_String", my_method_int.depends_on)
        self.assertNotIn("com.example.MyClass.myMethod_String", my_method_str.depends_on)
        
        # myMethod(int, String) depends on Student and helperMethod
        self.assertIn("com.example.model.Student", my_method_int.depends_on)
        self.assertIn("com.example.MyClass.helperMethod", my_method_int.depends_on)
        
        # Phase C tests - Graph Integration
        graph = build_graph_from_components(components)
        sorted_components = dependency_first_dfs(graph)
        
        self.assertEqual(len(sorted_components), len(components), "All components must be in sorted graph")
        
        # In a valid dependency-first sort, dependencies should appear BEFORE dependents
        # For example, MyClass depends on MyInterface
        interface_idx = sorted_components.index("com.example.MyInterface")
        class_idx = sorted_components.index("com.example.MyClass")
        self.assertTrue(interface_idx < class_idx, "MyInterface should come before MyClass in sorted graph")
        
        # Student should come before myMethod_int_String
        student_idx = sorted_components.index("com.example.model.Student")
        method_idx = sorted_components.index("com.example.MyClass.myMethod_int_String")
        self.assertTrue(student_idx < method_idx, "Student should come before myMethod_int_String")

        # ClassA and ClassB have circular dependency. Sorting should not crash and both should be present.
        self.assertIn("com.example.ClassA", sorted_components)
        self.assertIn("com.example.ClassB", sorted_components)
        
        # Verify Repeatability
        parser_2 = JavaDependencyParser(str(self.test_dir))
        components_2 = parser_2.parse_repository()
        self.assertEqual(set(components.keys()), set(components_2.keys()), "Successive parses should yield identical component IDs")
        for cid in components:
            self.assertEqual(components[cid].depends_on, components_2[cid].depends_on, f"Dependencies for {cid} differ between parses")
        
        print("Success! All parser and graph integration tests passed.")

if __name__ == "__main__":
    unittest.main()
