import os
import logging
from typing import List, Tuple
import tree_sitter
import tree_sitter_java

from .ast_parser import CodeComponent

logger = logging.getLogger(__name__)

try:
    JAVA_LANGUAGE = tree_sitter.Language(tree_sitter_java.language())
except Exception as e:
    logger.error(f"Failed to load tree-sitter-java: {e}")
    JAVA_LANGUAGE = None

class JavaInserter:
    """
    Handles safe insertion of Javadoc comments into Java source files.
    """
    
    def __init__(self):
        if JAVA_LANGUAGE:
            self.parser = tree_sitter.Parser(JAVA_LANGUAGE)
        else:
            self.parser = None

    def format_javadoc(self, docstring: str, indent: str) -> str:
        """
        Format a raw docstring into a proper Javadoc comment.
        """
        docstring = docstring.strip()
        
        # Strip existing Javadoc markers if the LLM provided them
        if docstring.startswith('/**'):
            docstring = docstring[3:]
        if docstring.endswith('*/'):
            docstring = docstring[:-2]
            
        docstring = docstring.strip()
        if not docstring:
            return ""
            
        # Sanitize invalid terminators inside the docstring
        docstring = docstring.replace('*/', '* /')
        
        lines = docstring.split('\n')
        formatted_lines = ['/**']
        for line in lines:
            line_str = line.strip()
            # If the LLM already included '* ', don't duplicate it
            if line_str.startswith('*'):
                formatted_lines.append(f" {line_str}")
            else:
                formatted_lines.append(f" * {line_str}" if line_str else " *")
        formatted_lines.append(" */")
        
        # Apply indentation
        result = "\n".join(indent + line if i > 0 else line for i, line in enumerate(formatted_lines))
        return result + "\n" + indent

    def get_indentation(self, source: bytes, start_byte: int) -> str:
        """
        Extract the indentation spaces before a given byte offset.
        """
        i = start_byte - 1
        while i >= 0 and source[i] not in (ord('\n'), ord('\r')):
            i -= 1
        indent_bytes = source[i+1:start_byte]
        # Only keep whitespace
        indent_str = "".join(c for c in indent_bytes.decode('utf-8', errors='ignore') if c.isspace())
        return indent_str

    def insert_javadocs(self, file_path: str, insertions: List[Tuple[CodeComponent, str]]) -> bool:
        """
        Insert multiple Javadocs into a Java file safely and transactionally.
        Returns True if successful and written to file, False otherwise.
        """
        if not self.parser:
            logger.error("Tree-sitter Java not available.")
            return False
            
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
            
        try:
            with open(file_path, 'rb') as f:
                source_bytes = f.read()
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return False
            
        # Parse original to check for baseline errors
        original_tree = self.parser.parse(source_bytes)
        original_had_error = original_tree.root_node.has_error
            
        # Filter and sort insertions descending by start_byte
        valid_insertions = []
        for comp, doc in insertions:
            if comp.has_docstring:
                logger.info(f"Skipping {comp.id}: already has docstring.")
                continue
            if not comp.node:
                logger.warning(f"Skipping {comp.id}: no AST node available.")
                continue
            valid_insertions.append((comp, doc))
            
        valid_insertions.sort(key=lambda x: x[0].node.start_byte, reverse=True)
        
        if not valid_insertions:
            return True # Nothing to do, consider it success
            
        modified_bytes = source_bytes
        
        for comp, doc in valid_insertions:
            start_byte = comp.node.start_byte
            indent = self.get_indentation(source_bytes, start_byte)
            javadoc_str = self.format_javadoc(doc, indent)
            
            if not javadoc_str:
                continue
                
            javadoc_bytes = javadoc_str.encode('utf-8')
            modified_bytes = modified_bytes[:start_byte] + javadoc_bytes + modified_bytes[start_byte:]
            
        # Validation step
        new_tree = self.parser.parse(modified_bytes)
        if new_tree.root_node.has_error and not original_had_error:
            logger.error(f"Validation failed: insertion introduced syntax errors in {file_path}.")
            logger.error(f"Modified source:\n{modified_bytes.decode('utf-8', errors='replace')}")
            return False
            
        # Write back
        try:
            with open(file_path, 'wb') as f:
                f.write(modified_bytes)
            return True
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
            return False
