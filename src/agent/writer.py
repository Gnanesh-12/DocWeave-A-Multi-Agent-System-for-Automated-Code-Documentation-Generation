# Copyright (c) Meta Platforms, Inc. and affiliates
import re
from typing import Dict, Any, Optional
from abc import abstractmethod
from .base import BaseAgent
from .reader import CodeComponentType
from ..dependency_analyzer.javadoc_sanitizer import tag_requirements

class Writer(BaseAgent):
    """Agent responsible for generating high-quality docstrings based on the code and context."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the Writer agent.
        
        Args:
            config_path: Optional path to the configuration file
        """
        super().__init__("Writer", config_path=config_path)

        # Language of the component being documented: "python" or "java".
        # Set per component by generate_docstrings.py; selects the prompts below.
        self.language = "python"
        
        # Base prompt that applies to all documentation
        self.base_prompt = """You are a Writer agent responsible for generating high-quality 
        docstrings that are both complete and helpful. Accessible context is provided to you for 
        generating the docstring.
        
        General Guidelines:
        1. Make docstrings actionable and specific:
           - Focus on practical usage
           - Highlight important considerations
           - Include warnings or gotchas
        
        2. Use clear, concise language:
           - Avoid jargon unless necessary
           - Use active voice
           - Be direct and specific
        
        3. Type Information:
           - Include precise type hints
           - Note any type constraints
           - Document generic type parameters
        
        4. Context and Integration:
           - Explain component relationships
           - Note any dependencies
           - Describe side effects
        
        5. Follow Google docstring format:
           - Use consistent indentation
           - Maintain clear section separation
           - Keep related information grouped"""

        self.add_to_memory("system", self.base_prompt)

        # Class-specific prompt
        self.class_prompt = """You are documenting a CLASS. Focus on describing the object it represents 
        and its role in the system.

        Required sections:
        1. Summary: 
           - One-line description focusing on WHAT the class represents
           - Avoid repeating the class name or obvious terms
           - Focus on the core purpose or responsibility
        
        2. Description: 
           - WHY: Explain the motivation and purpose behind this class
           - WHEN: Describe scenarios or conditions where this class should be used
           - WHERE: Explain how it fits into the larger system architecture
           - HOW: Provide a high-level overview of how it achieves its purpose
        
        3. Example: 
           - Show a practical, real-world usage scenario
           - Include initialization and common method calls
           - Demonstrate typical workflow

        Conditional sections:
        1. Parameters (if class's __init__ has parameters):
           - Focus on explaining the significance of each parameter
           - Include valid value ranges or constraints
           - Explain parameter relationships if they exist
        
        2. Attributes:
           - Explain the purpose and significance of each attribute
           - Include type information and valid values
           - Note any dependencies between attributes"""

        # Function/Method-specific prompt
        self.function_prompt = """You are documenting a FUNCTION or METHOD. Focus on describing 
        the action it performs and its effects.

        Required sections:
        1. Summary:
           - One-line description focusing on WHAT the function does
           - Avoid repeating the function name
           - Emphasize the outcome or effect
        
        2. Description:
           - WHY: Explain the purpose and use cases
           - WHEN: Describe when to use this function
           - WHERE: Explain how it fits into the workflow
           - HOW: Provide high-level implementation approach

        Conditional sections:
        1. Args (if present):
           - Explain the significance of each parameter
           - Include valid value ranges or constraints
           - Note any parameter interdependencies
        
        2. Returns:
           - Explain what the return value represents
           - Include possible return values or ranges
           - Note any conditions affecting the return value
        
        3. Raises:
           - List specific conditions triggering each exception
           - Explain how to prevent or handle exceptions
        
        4. Examples (if public and not abstract):
           - Show practical usage scenarios
           - Include common parameter combinations
           - Demonstrate error handling if relevant"""

        # Java prompts. Kept self-contained and sent with every request (rather than
        # only as the system message) because the system message can be dropped when
        # the Writer's memory is cleared.
        self.java_base_prompt = """You are documenting JAVA code. Write the body of a standard Javadoc comment.

        Format rules:
        1. Do NOT include the /** and */ markers or leading asterisks; they are added automatically.
        2. Start with a one-sentence summary that ends with a period. Leave a blank line, then add details if needed.
        3. Use ONLY standard Javadoc block tags: @param, @return, @throws (and @param <T> for type parameters).
           Never invent tags such as @summary, @description, @when, @where, @how or @example.
           Do not use @since, @author, @version or @see.
        4. Do not use Python conventions or terms: no "Args:", "Returns:", "Raises:", "self", "__init__", or docstring sections.
        5. Do not use markdown (no backticks, no code fences). Use {@code ...} for inline code and <pre>{@code ...}</pre> for an example, only when it helps.
        6. Document only what the code shows. Never invent parameters, return values or exceptions.
        7. Use plain, specific language and Java terminology (method, constructor, field, interface, record)."""

        self.java_class_prompt = """You are documenting a Java CLASS, INTERFACE, ENUM or RECORD.

        Describe:
        - Summary: what the type represents, in one sentence, without just repeating its name.
        - Details: its role and responsibility, where it fits in the system, and how it is typically used.

        Tag rules for a type:
        - Do NOT use @return or @throws; those belong to methods.
        - Do NOT document a method's parameters here. Do not describe the type as if it were a single method.
        - For a RECORD, add one @param line per record component.
        - For a generic type, add one @param <T> line per type parameter."""

        self.java_method_prompt = """You are documenting a Java METHOD or CONSTRUCTOR.

        Describe:
        - Summary: what it does (or, for a constructor, what it creates), in one sentence.
        - Details: when to use it, important behaviour, side effects and thread-safety if relevant.

        Tag rules:
        - One @param line per parameter, in order, explaining its meaning and any constraints.
        - @return only if the method does not return void; never for a constructor.
        - @throws only for an exception that appears in the code as a 'throws' clause or a 'throw new' statement.
          If neither appears, write no @throws line at all."""

    @staticmethod
    def java_required_tags(code: str) -> str:
        """Spell out which Javadoc tags this declaration needs; a 7B model skips them otherwise."""
        header = "REQUIRED TAGS FOR THIS COMPONENT:"
        sep = "\n        "
        if Writer.is_java_type_declaration(code):
            params, _, _ = tag_requirements(code)
            if params:
                return header + sep + f"- Add one '@param <name> <description>' line for each record component: {', '.join(params)}."
            return header + sep + "- Write no @param, @return or @throws tags."
        params, needs_return, exceptions = tag_requirements(code)
        lines = []
        if params:
            lines.append(f"- Add one '@param <name> <description>' line for each parameter, in this order: {', '.join(params)}.")
        else:
            lines.append("- It has NO parameters: write no @param lines.")
        lines.append("- Add an '@return <description>' line." if needs_return else "- Write no @return line.")
        if exceptions:
            lines.append(f"- Add '@throws <Exception> <reason>' for each of: {', '.join(sorted(exceptions))}.")
        else:
            lines.append("- Write no @throws line.")
        return header + sep + sep.join(lines)

    def complete_java_tags(self, code: str, docstring: str) -> str:
        """Ask for any @param/@return lines the model left out, in one short focused call.

        Skipped tags are the 7B model's most common Javadoc gap and it ignores the
        required-tags list, but it handles a narrow "write just these lines" request.
        """
        params, needs_return, _ = tag_requirements(code)
        present = set(re.findall(r'^\s*\*?\s*@param\s+(\S+)', docstring, flags=re.M))
        missing_params = [p for p in params if p not in present]
        missing_return = needs_return and not re.search(r'^\s*\*?\s*@return\b', docstring, flags=re.M)
        if not missing_params and not missing_return:
            return docstring

        wanted = [f"@param {p} <one-sentence description>" for p in missing_params]
        if missing_return:
            wanted.append("@return <one-sentence description of the returned value>")
        wanted_text = "\n".join(wanted)
        prompt = (
            "Here is a Java declaration:\n\n"
            f"{code}\n\n"
            "Write ONLY the following Javadoc tag lines, one per line, replacing each <...> with a short, "
            "specific description based on the code. No other text, no markdown.\n\n"
            f"{wanted_text}"
        )
        try:
            response = self.generate_response(messages=[self.llm.format_message("user", prompt)])
        except Exception:
            return docstring

        keep = []
        for line in response.splitlines():
            line = line.strip().lstrip('*').strip()
            match = re.match(r'@(param|return)\b\s*(\S*)', line)
            if not match or '<one-sentence' in line or '<description' in line:
                continue
            if match.group(1) == 'param' and match.group(2) in missing_params:
                keep.append(line)
            elif match.group(1) == 'return' and missing_return:
                keep.append(line)
        if not keep:
            return docstring
        return docstring.rstrip() + "\n\n" + "\n".join(keep)

    @staticmethod
    def is_java_type_declaration(code: str) -> bool:
        """Return True if Java source declares a class, interface, enum or record.

        Looks at the declaration head (text before the first '{'), ignoring leading
        annotations, so an annotated class such as @RestController is still detected.
        """
        head = code.split('{', 1)[0]
        head = re.sub(r'@\w+(?:\.\w+)*(?:\([^)]*\))?', ' ', head)
        match = re.search(r'(?<![\w.])(class|interface|enum|record)\s+[A-Za-z_]\w*', head)
        return bool(match) and '(' not in head[:match.start()]

    def is_class_component(code: str) -> bool:
        """Determine if the given code component is a class definition.
        
        Args:
            code: The code component to analyze
            
        Returns:
            bool: True if the component is a class definition, False otherwise
        """
        return "class " in code.split('\n')[0]

    def get_custom_prompt(self, code: str) -> str:
        """Get the appropriate system prompt based on the component type.
        
        Args:
            code: The code component to analyze
            
        Returns:
            str: The appropriate system prompt for the component type
        """
        if self.language == "java":
            is_type = Writer.is_java_type_declaration(code)
            return self.java_class_prompt if is_type else self.java_method_prompt
        is_class = Writer.is_class_component(code)
        specific_prompt = self.class_prompt if is_class else self.function_prompt
        return specific_prompt

    def extract_docstring(self, response: str) -> str:
        """Extract the docstring from the LLM response.
        
        Args:
            response: The full response from the LLM containing the docstring between XML tags
            
        Returns:
            str: The extracted docstring, or empty string if no docstring found
        """
        start_tag = "<DOCSTRING>"
        end_tag = "</DOCSTRING>"
        
        try:
            start_idx = response.index(start_tag) + len(start_tag)
            end_idx = response.index(end_tag)
            return response[start_idx:end_idx].strip()
        except ValueError:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("\033[93mError parsing, no DOCSTRING XML tags found in response, directly return the response as docstring %s\033[0m")
            return response

    def process(
        self,
        focal_component: str,
        context: Dict[str, Any],
    ) -> str:
        """Generate a docstring for the given code component.
        
        Args:
            focal_component: The code component needing a docstring
            context: Dictionary containing gathered context information
            
        Returns:
            str: The generated docstring following the specified format
        """
        
        java_rules = ""
        if self.language == "java":
            java_rules = f"{self.java_base_prompt}\n\n        {self.java_required_tags(focal_component)}\n\n        "

        task_description = f"""
        Available context:
        {context}

        {java_rules}{self.get_custom_prompt(focal_component)}

        Now, generate a high-quality docstring for the following Code Component based on the Available context:
        
        <FOCAL_CODE_COMPONENT>
        {focal_component}
        </FOCAL_CODE_COMPONENT>

        Keep in mind:
        1. Generate docstring between XML tag: <DOCSTRING> and </DOCSTRING>
        2. First analysis the code component and then generate the docstring at the end based on the context.
        3. Do not add triple quotes (\"\"\") or comment markers to your generated docstring.
        4. Always double check if the generated docstring is within the XML tags: <DOCSTRING> and </DOCSTRING>. This is critical for parsing the docstring.
        """
        self.add_to_memory("user", task_description)
        
        # Generate response using LLM
        full_response = self.generate_response()
        
        # Extract and return just the docstring part
        docstring = self.extract_docstring(full_response)
        if self.language == "java":
            docstring = self.complete_java_tags(focal_component, docstring)
        return docstring
    
