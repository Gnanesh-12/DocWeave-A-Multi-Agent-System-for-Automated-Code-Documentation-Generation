import os
import re
import logging
from typing import Dict, List, Set, Optional, Any
import tree_sitter
import tree_sitter_java

from .ast_parser import CodeComponent

logger = logging.getLogger(__name__)

try:
    JAVA_LANGUAGE = tree_sitter.Language(tree_sitter_java.language())
except Exception as e:
    logger.error(f"Failed to load tree-sitter-java: {e}")
    JAVA_LANGUAGE = None

# Common Java standard types to ignore when building project-local dependencies
BUILTIN_TYPES = {
    'String', 'Object', 'Integer', 'Boolean', 'Double', 'Float', 'Long', 'Short', 'Byte', 'Character',
    'int', 'boolean', 'double', 'float', 'long', 'short', 'byte', 'char', 'void',
    'List', 'Map', 'Set', 'Collection', 'Optional', 'Stream', 'Array', 'Arrays', 'Collections',
    'Exception', 'RuntimeException', 'Throwable', 'Error', 'System', 'out'
}

class JavaDependencyParser:
    """
    Parses Java code using Tree-sitter to build a dependency graph between code components.
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.components: Dict[str, CodeComponent] = {}
        if JAVA_LANGUAGE:
            self.parser = tree_sitter.Parser(JAVA_LANGUAGE)
        else:
            self.parser = None
            
        self.modules: Set[str] = set()
        self._reset_state()

        # Multi-module repos (e.g. initial/ and complete/ copies of one project) can
        # declare the same fully qualified name twice. When that happens the repo is
        # re-parsed with each component ID prefixed by its module directory.
        self._prefix_modules = False
        self._id_collision = False

    def _reset_state(self):
        self.components = {}
        self.modules = set()
        # Helper structures for resolving dependencies
        self.file_package: Dict[str, str] = {}
        self.file_module: Dict[str, str] = {}
        self.file_imports: Dict[str, Dict[str, str]] = {}
        self.project_classes: Dict[str, Dict[str, str]] = {}  # unqualified_name -> {module: component_id}

    def _module_for(self, relative_path: str) -> str:
        """Module directory (path before 'src') as a dot-free ID prefix, or '' when not prefixing."""
        if not self._prefix_modules:
            return ""
        parts = relative_path.replace("\\", "/").split("/")
        module_parts = parts[:parts.index("src")] if "src" in parts else parts[:-1]
        return re.sub(r'[^A-Za-z0-9-]+', '-', "/".join(module_parts)).strip('-')

    def _qualify(self, module: str, fqn: str) -> str:
        return f"{module}.{fqn}" if module else fqn

    def _register(self, comp_id: str, component: CodeComponent):
        existing = self.components.get(comp_id)
        if existing is not None and existing.file_path != component.file_path:
            self._id_collision = True
        self.components[comp_id] = component

    def parse_repository(self) -> Dict[str, CodeComponent]:
        if not self.parser:
            logger.error("Tree-sitter Java not initialized. Cannot parse repository.")
            return {}
            
        logger.info(f"Parsing Java repository at {self.repo_path}")

        self._scan_files()
        if self._id_collision and not self._prefix_modules:
            logger.info("Duplicate Java component IDs across modules; re-parsing with module prefixes")
            self._prefix_modules = True
            self._reset_state()
            self._scan_files()

        # Pass 2: Resolve dependencies using the collected components and imports
        self._resolve_dependencies()
        
        # Pass 3: Classes depend on their methods
        self._add_class_method_dependencies()
        
        logger.info(f"Found {len(self.components)} Java code components")
        return self.components

    def _scan_files(self):
        # Pass 1: Collect files, packages, imports, and component definitions
        for root, _, files in os.walk(self.repo_path):
            # Exclude common build directories
            if any(part in root.split(os.sep) for part in ['.git', 'target', 'build', 'node_modules', 'bin']):
                continue
                
            for file in files:
                if file.endswith(".java"):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.repo_path)
                    self._parse_file(file_path, relative_path)

    def _parse_file(self, file_path: str, relative_path: str):
        try:
            with open(file_path, "rb") as f:
                source_bytes = f.read()
            source = source_bytes.decode('utf-8', errors='replace')
            tree = self.parser.parse(source_bytes)
            
            package_name = ""
            imports = {}
            
            # Find package and imports
            for child in tree.root_node.children:
                if child.type == 'package_declaration':
                    pkg_node = next((n for n in child.children if n.type in ('scoped_identifier', 'identifier')), None)
                    if pkg_node:
                        package_name = pkg_node.text.decode('utf-8')
                elif child.type == 'import_declaration':
                    import_node = next((n for n in child.children if n.type in ('scoped_identifier', 'identifier')), None)
                    if import_node:
                        full_import = import_node.text.decode('utf-8')
                        class_name = full_import.split('.')[-1]
                        imports[class_name] = full_import
                        
            self.file_package[file_path] = package_name
            self.file_imports[file_path] = imports
            if package_name:
                self.modules.add(package_name)
            module = self._module_for(relative_path)
            self.file_module[file_path] = module
            
            # Extract components recursively
            self._collect_components(tree.root_node, file_path, relative_path,
                                     self._qualify(module, package_name), source, source_bytes)
            
        except Exception as e:
            logger.warning(f"Error parsing {file_path}: {e}")

    def _get_method_signature_suffix(self, node: tree_sitter.Node) -> str:
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

    def _collect_components(self, node: tree_sitter.Node, file_path: str, relative_path: str, 
                          current_prefix: str, source: str, source_bytes: bytes):
        
        for child in node.children:
            if child.type in ('class_declaration', 'interface_declaration', 'enum_declaration', 'record_declaration'):
                name_node = next((n for n in child.children if n.type == 'identifier'), None)
                if not name_node:
                    continue
                name = name_node.text.decode('utf-8')
                
                comp_id = f"{current_prefix}.{name}" if current_prefix else name
                
                javadoc = self._get_javadoc(child)
                has_javadoc = bool(javadoc)
                
                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                
                comp_type = "class"
                if child.type == 'interface_declaration': comp_type = "interface"
                elif child.type == 'enum_declaration': comp_type = "enum"
                elif child.type == 'record_declaration': comp_type = "record"
                
                source_code = source_bytes[child.start_byte:child.end_byte].decode('utf-8', errors='replace')
                
                component = CodeComponent(
                    id=comp_id,
                    node=child,
                    component_type=comp_type,
                    file_path=file_path,
                    relative_path=relative_path,
                    source_code=source_code,
                    start_line=start_line,
                    end_line=end_line,
                    has_docstring=has_javadoc,
                    docstring=javadoc
                )
                
                self._register(comp_id, component)
                self.project_classes.setdefault(name, {})[self.file_module.get(file_path, "")] = comp_id
                
                # Nested traversal
                body_node = next((n for n in child.children if n.type in ('class_body', 'interface_body', 'enum_body', 'record_body')), None)
                if body_node:
                    self._collect_components(body_node, file_path, relative_path, comp_id, source, source_bytes)
                    
            elif child.type in ('method_declaration', 'constructor_declaration'):
                name_node = next((n for n in child.children if n.type == 'identifier'), None)
                if not name_node:
                    continue
                name = name_node.text.decode('utf-8')
                
                suffix = self._get_method_signature_suffix(child)
                comp_id = f"{current_prefix}.{name}{suffix}" if current_prefix else f"{name}{suffix}"
                
                javadoc = self._get_javadoc(child)
                has_javadoc = bool(javadoc)
                
                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                
                comp_type = "method" if child.type == 'method_declaration' else "constructor"
                
                source_code = source_bytes[child.start_byte:child.end_byte].decode('utf-8', errors='replace')
                
                component = CodeComponent(
                    id=comp_id,
                    node=child,
                    component_type=comp_type,
                    file_path=file_path,
                    relative_path=relative_path,
                    source_code=source_code,
                    start_line=start_line,
                    end_line=end_line,
                    has_docstring=has_javadoc,
                    docstring=javadoc
                )
                
                self._register(comp_id, component)
                
            else:
                # Traverse further down for other nodes, just in case (e.g. nested blocks)
                self._collect_components(child, file_path, relative_path, current_prefix, source, source_bytes)

    def _get_javadoc(self, node: tree_sitter.Node) -> str:
        prev = node.prev_sibling
        if prev and prev.type == 'block_comment':
            text = prev.text.decode('utf-8')
            if text.startswith('/**'):
                return text
        return ""

    def _extract_type_references(self, node: tree_sitter.Node, refs: Set[str]):
        if node.type in ('type_identifier', 'identifier', 'scoped_identifier'):
            refs.add(node.text.decode('utf-8'))
        for child in node.children:
            self._extract_type_references(child, refs)

    def _resolve_dependencies(self):
        for comp_id, component in self.components.items():
            node = component.node
            if not node:
                continue
                
            raw_refs = set()
            
            if component.component_type in ('class', 'interface', 'enum', 'record'):
                for child in node.children:
                    if child.type in ('superclass', 'super_interfaces'):
                        self._extract_type_references(child, raw_refs)
            elif component.component_type in ('method', 'constructor'):
                self._extract_type_references(node, raw_refs)
                
            file_path = component.file_path
            pkg = self.file_package.get(file_path, "")
            mod = self.file_module.get(file_path, "")
            imports = self.file_imports.get(file_path, {})
            
            for ref in raw_refs:
                if ref in BUILTIN_TYPES:
                    continue
                    
                # 1. Check if imported
                if ref in imports:
                    full_ref = self._qualify(mod, imports[ref])
                    if full_ref in self.components:
                        component.depends_on.add(full_ref)
                    continue
                    
                # 2. Check if in the same package
                same_pkg_ref = self._qualify(mod, f"{pkg}.{ref}" if pkg else ref)
                if same_pkg_ref in self.components:
                    component.depends_on.add(same_pkg_ref)
                    continue
                    
                # 3. Check if sibling method
                if component.component_type in ('method', 'constructor'):
                    class_id = ".".join(comp_id.split('.')[:-1])
                    sibling_prefix = f"{class_id}.{ref}"
                    # Match any overloaded method variants
                    for cid in self.components:
                        if cid == sibling_prefix or cid.startswith(f"{sibling_prefix}_"):
                            component.depends_on.add(cid)
                        
                # 4. Check if project class
                if ref in self.project_classes:
                    candidates = self.project_classes[ref]
                    component.depends_on.add(candidates.get(mod) or next(iter(candidates.values())))
                    continue
                    
                # 5. Scoped identifiers
                if '.' in ref:
                    if self._qualify(mod, ref) in self.components:
                        component.depends_on.add(self._qualify(mod, ref))
                    elif self._qualify(mod, f"{pkg}.{ref}") in self.components:
                        component.depends_on.add(self._qualify(mod, f"{pkg}.{ref}"))
            
            # Filter out self-dependencies
            component.depends_on.discard(comp_id)

    def _add_class_method_dependencies(self):
        class_methods = {}
        for component_id, component in self.components.items():
            if component.component_type == "method":
                parts = component_id.split(".")
                if len(parts) >= 2:
                    class_id = ".".join(parts[:-1])
                    if class_id not in class_methods:
                        class_methods[class_id] = []
                    class_methods[class_id].append(component_id)
                    
        for class_id, method_ids in class_methods.items():
            if class_id in self.components:
                class_component = self.components[class_id]
                for method_id in method_ids:
                    class_component.depends_on.add(method_id)
