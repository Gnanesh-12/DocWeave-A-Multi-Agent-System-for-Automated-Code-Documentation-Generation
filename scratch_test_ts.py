import tree_sitter
import tree_sitter_java

JAVA_LANGUAGE = tree_sitter.Language(tree_sitter_java.language())
parser = tree_sitter.Parser(JAVA_LANGUAGE)

source_code = b"""
package com.example;

import java.util.List;
import com.example.model.Student;

/**
 * Represents a class.
 */
public class MyClass extends BaseClass implements MyInterface {
    
    private Student student;
    
    /**
     * Constructor
     */
    public MyClass() {
        super();
    }
    
    public int myMethod(int a, String b) {
        Student s = new Student();
        return a;
    }
}
"""

tree = parser.parse(source_code)
root = tree.root_node

def get_method_signature_suffix(node):
    params_node = next((n for n in node.children if n.type == 'formal_parameters'), None)
    if not params_node:
        return ""
    
    type_names = []
    for param in params_node.children:
        if param.type in ('formal_parameter', 'spread_parameter'):
            type_child = param.child_by_field_name('type')
            if type_child:
                type_names.append(type_child.text.decode('utf-8').replace(' ', '_').replace('[]', 'Array'))
            else:
                if param.children:
                    type_names.append(param.children[0].text.decode('utf-8').replace(' ', '_').replace('[]', 'Array'))
    
    if type_names:
        return "_" + "_".join(type_names)
    return ""

def walk(node):
    if node.type == 'method_declaration':
        print(f"Method: {node.child_by_field_name('name').text.decode('utf-8')}")
        print(f"Suffix: {get_method_signature_suffix(node)}")
    for child in node.children:
        walk(child)

walk(root)

