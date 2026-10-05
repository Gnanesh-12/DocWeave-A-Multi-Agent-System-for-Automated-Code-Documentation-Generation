"""Deterministic clean-up of LLM-written Javadoc before it is inserted.

Small local models ignore prompt rules (invented @since/@throws, tags on the wrong
kind of component, markdown), so the output is checked against the code itself: a
tag is kept only if the declaration backs it up, and markdown becomes Javadoc markup.
"""
import re
from typing import List, Optional, Set, Tuple

ALLOWED_TAGS = {"param", "return", "throws", "exception"}
_ANNOTATION = re.compile(r'@\w+(?:\.\w+)*(?:\([^()]*\))?')
_TAG_LINE = re.compile(r'^\s*\*?\s*@(\w+)\b\s*(.*)$')
_MODIFIERS = {
    'public', 'protected', 'private', 'static', 'final', 'abstract', 'synchronized',
    'native', 'default', 'strictfp', 'transient', 'volatile',
}
_PLACEHOLDER = "\x00{}\x00"


def _declaration_head(source: str) -> str:
    """Source up to the first '{' or ';' that is not inside parentheses."""
    depth = 0
    for i, ch in enumerate(source):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch in '{;' and depth == 0:
            return source[:i]
    return source


def _top_level_split(text: str) -> List[str]:
    """Split on commas that are not inside <> or ()."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch in '<(':
            depth += 1
        elif ch in '>)':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return [p.strip() for p in parts if p.strip()]


def _parameter_list(head: str) -> List[str]:
    """Names declared in the first parameter list of a method, constructor or record."""
    head = _ANNOTATION.sub(' ', head)
    start = head.find('(')
    if start == -1:
        return []
    depth, end = 0, None
    for i in range(start, len(head)):
        if head[i] == '(':
            depth += 1
        elif head[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return []
    names = []
    for param in _top_level_split(head[start + 1:end]):
        match = re.search(r'(\w+)\s*(?:\[\s*\])*\s*$', param)
        if match:
            names.append(match.group(1))
    return names


def _type_parameters(head: str) -> Set[str]:
    """Type parameter names such as T and K from 'class Box<T, K extends Foo>'."""
    match = re.search(r'(?:class|interface|record|enum)\s+\w+\s*<(.*)>', head)
    if not match:
        return set()
    return {re.match(r'\w+', p).group(0) for p in _top_level_split(match.group(1)) if re.match(r'\w+', p)}


def _declared_exceptions(source: str, head: str) -> Set[str]:
    """Exception simple names from the 'throws' clause and 'throw new X' statements."""
    names = set()
    throws = re.search(r'\)\s*throws\s+([^{;]+)', head)
    if throws:
        names.update(n.strip().split('.')[-1] for n in throws.group(1).split(',') if n.strip())
    names.update(m.split('.')[-1] for m in re.findall(r'\bthrow\s+new\s+([\w.]+)', source))
    return names


def _infer_kind(head: str) -> str:
    """'record', 'type', 'constructor' or 'method' from a declaration head."""
    plain = _ANNOTATION.sub(' ', head)
    before_paren = plain.split('(', 1)[0]
    match = re.search(r'(?<![\w.])(class|interface|enum|record)\s+\w+', before_paren)
    if match:
        return 'record' if match.group(1) == 'record' else 'type'
    words = [w for w in re.findall(r'[\w<>\[\].?]+', re.sub(r'<[^()]*?>', '', before_paren)) if w not in _MODIFIERS]
    return 'constructor' if len(words) <= 1 else 'method'


def tag_requirements(source: str) -> Tuple[List[str], bool, Set[str]]:
    """Tags the code calls for: (parameter names in order, needs @return, declared exceptions)."""
    head = _declaration_head(source)
    kind = _infer_kind(head)
    if kind == 'type':
        return [], False, set()
    names = _parameter_list(head)
    if kind == 'record':
        return names, False, set()
    is_void = bool(re.search(r'\bvoid\s+\w+\s*\(', _ANNOTATION.sub(' ', head)))
    return names, kind == 'method' and not is_void, _declared_exceptions(source, head)


def _to_javadoc_html(text: str) -> str:
    """Convert markdown the model tends to emit into Javadoc-friendly markup."""
    def fence(match):
        body = match.group(1).strip('\n')
        body = body.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return "<pre>\n" + body + "\n</pre>"

    text = re.sub(r'```[A-Za-z]*\n(.*?)```', fence, text, flags=re.S)

    def inline(match):
        code = match.group(1)
        if '{' in code or '}' in code:
            return code
        return '{@code ' + code + '}'

    return re.sub(r'`([^`\n]+)`', inline, text)


def _paragraphs(text: str) -> str:
    """Javadoc ignores blank lines; mark paragraph breaks with <p> (outside <pre>)."""
    pres: List[str] = []

    def stash(match):
        pres.append(match.group(0))
        return _PLACEHOLDER.format(len(pres) - 1)

    text = re.sub(r'<pre>.*?</pre>', stash, text, flags=re.S)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    text = '\n\n'.join(paragraphs[:1] + [p if p.startswith('\x00') else '<p>' + p for p in paragraphs[1:]])
    return re.sub('\x00(\\d+)\x00', lambda m: pres[int(m.group(1))], text)


def sanitize_javadoc(docstring: str, component) -> str:
    """Drop tags that the component's code does not justify; return the cleaned body."""
    source = getattr(component, 'source_code', '') or ''
    comp_type = getattr(component, 'component_type', '')
    head = _declaration_head(source)
    is_type = comp_type in ('class', 'interface', 'enum', 'record')
    is_void = bool(re.search(r'\bvoid\s+\w+\s*\(', _ANNOTATION.sub(' ', head)))

    if is_type:
        valid_params = set(_parameter_list(head)) if comp_type == 'record' else set()
        valid_params |= {f"<{t}>" for t in _type_parameters(head)}
    else:
        valid_params = set(_parameter_list(head))
    exceptions = _declared_exceptions(source, head)

    description: List[str] = []
    blocks: List[List[str]] = []
    seen_params: Set[str] = set()
    keep_current: Optional[bool] = None

    for line in docstring.strip().splitlines():
        tag = _TAG_LINE.match(line)
        if tag:
            name, rest = tag.group(1), tag.group(2).strip()
            keep = name in ALLOWED_TAGS
            if keep and name == 'param':
                target = rest.split()[0] if rest else ''
                keep = target in valid_params and target not in seen_params
                if keep:
                    seen_params.add(target)
            elif keep and name == 'return':
                keep = not is_type and comp_type != 'constructor' and not is_void
            elif keep and name in ('throws', 'exception'):
                target = rest.split()[0].split('.')[-1] if rest else ''
                keep = not is_type and target in exceptions
            keep_current = keep
            if keep:
                blocks.append([line.rstrip()])
        elif keep_current is None:
            description.append(line.rstrip())
        elif keep_current and blocks:
            blocks[-1].append(line.rstrip())

    description_text = _paragraphs(_to_javadoc_html('\n'.join(description).strip()))
    result = description_text.split('\n') if description_text else []
    if blocks:
        if result:
            result.append('')
        declared = _parameter_list(head)

        def order(block):
            tag = _TAG_LINE.match(block[0])
            name, rest = tag.group(1), tag.group(2).split()
            if name == 'param':
                target = rest[0] if rest else ''
                return (0, declared.index(target) if target in declared else len(declared))
            return (1 if name == 'return' else 2, 0)

        for block in sorted(blocks, key=order):
            while block and not block[-1].strip():
                block.pop()
            result.extend(block)
    return re.sub(r'\n[ \t]*(?:\n[ \t]*)+', '\n\n', '\n'.join(result)).strip()
