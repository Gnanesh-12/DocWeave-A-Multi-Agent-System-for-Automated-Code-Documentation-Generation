"""Local LLM-judge for docstring truthfulness.

For each documented class/function/method in the given file(s), asks a judge
LLM (configured the same way as DocWeave's agents, e.g. via a local Ollama
config) whether the docstring's claims (behavior, parameters, return value,
exceptions) are factually consistent with the code. Meant as a lightweight,
free alternative to src/evaluator/truthfulness.py and helpfulness_evaluator.py,
which are hardcoded to Gemini/OpenAI and to the paper's own experiment data.

Usage:
    python judge_truthfulness.py <file1.py> [file2.py ...] --config-path config/agent_config_qwen.yaml
"""
import argparse
import ast
import re
from pathlib import Path
from typing import Optional

from tabulate import tabulate

from src.agent.llm.factory import LLMFactory

SYSTEM_PROMPT = """You are a strict fact-checker for Python docstrings. You will be given a \
function/method/class's source code, including its docstring. Judge ONLY whether the docstring's \
factual claims (what it does, its parameters, return value, exceptions raised, and any example \
output) are consistent with what the code actually does. Do not judge style, completeness, or \
formatting - only factual accuracy.

Respond with your reasoning, then end with exactly:
<VERDICT>TRUTHFUL</VERDICT> if every claim matches the code,
<VERDICT>PARTIALLY_TRUTHFUL</VERDICT> if some claims are correct but others are wrong or invented,
<VERDICT>HALLUCINATED</VERDICT> if the docstring describes behavior, parameters, or exceptions the code does not have.

Then list any specific inaccuracies between <ISSUES> and </ISSUES> tags, one per line. If there are none, write "None" inside the tags."""


def extract_documented_components(source: str):
    """Yield (name, source_segment) for every class/function/method with a docstring."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            if not docstring or docstring.strip() == "No docstring provided.":
                continue
            segment = ast.get_source_segment(source, node)
            if segment:
                yield node.name, segment


_VERDICT_WORDS = r"(PARTIALLY_TRUTHFUL|HALLUCINATED|TRUTHFUL)"


def parse_verdict(response: str) -> tuple[str, str]:
    """Pull (verdict, issues) out of a judge response, tolerating sloppy tags.

    Small judges often write 'VERDICT:TRUTHFUL' or '<VERDICT>TRUTHFUL' instead of the exact
    '<VERDICT>...</VERDICT>', so accept any verdict word near the word VERDICT, else the last
    verdict word in the reply.
    """
    match = re.search(r"VERDICT\W{0,3}" + _VERDICT_WORDS, response, re.IGNORECASE)
    if not match:
        found = re.findall(r"\b" + _VERDICT_WORDS + r"\b", response, re.IGNORECASE)
        verdict = found[-1].upper() if found else "UNPARSEABLE"
    else:
        verdict = match.group(1).upper()
    issues_match = re.search(r"<ISSUES>(.*?)</ISSUES>", response, re.DOTALL)
    if issues_match:
        issues = issues_match.group(1).strip()
    else:
        tail = re.split(r"ISSUES\W*", response, maxsplit=1, flags=re.IGNORECASE)
        issues = (tail[1] if len(tail) > 1 else response).strip()[:200]
    return verdict, issues


def judge_component(llm, name: str, code_segment: str) -> tuple[str, str]:
    messages = [
        llm.format_message("system", SYSTEM_PROMPT),
        llm.format_message("user", f"Component: {name}\n\n```python\n{code_segment}\n```"),
    ]
    response = llm.generate(messages=messages, temperature=0.0, max_tokens=2048)
    return parse_verdict(response)


def judge_file(llm, file_path: str):
    source = Path(file_path).read_text(encoding="utf-8")
    rows = []
    for name, segment in extract_documented_components(source):
        verdict, issues = judge_component(llm, name, segment)
        rows.append([Path(file_path).name, name, verdict, issues])
    return rows


def main():
    parser = argparse.ArgumentParser(description="Judge docstring truthfulness with a local LLM.")
    parser.add_argument("files", nargs="+", help="Python file(s) to evaluate")
    parser.add_argument("--config-path", default="config/agent_config_qwen.yaml", help="LLM config to use as judge")
    args = parser.parse_args()

    config = LLMFactory.load_config(args.config_path)
    llm = LLMFactory.create_llm(config["llm"])

    all_rows = []
    for file_path in args.files:
        print(f"\nJudging {file_path} with {config['llm']['model']}...")
        all_rows.extend(judge_file(llm, file_path))

    print()
    print(tabulate(all_rows, headers=["File", "Component", "Verdict", "Issues"], tablefmt="grid", maxcolwidths=[None, None, None, 60]))

    counts = {}
    for row in all_rows:
        counts[row[2]] = counts.get(row[2], 0) + 1
    print("\nSummary:", counts)


if __name__ == "__main__":
    main()
