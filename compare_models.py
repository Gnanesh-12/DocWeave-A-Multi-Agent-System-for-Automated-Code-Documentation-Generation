"""Compare local Ollama models on DocWeave end to end, with one command.

For every installed candidate model it
  1. generates docstrings/Javadoc for each repo under eval_repos/ (timed),
  2. scores completeness (are sections/tags present?) and format compliance,
  3. has a *different* model judge truthfulness (is the doc consistent with the code?),
  4. writes a summary table (markdown + CSV) and per-component judgements.

Typical use, on a good connection:
    python compare_models.py --pull

Offline / already pulled:
    python compare_models.py

Everything runs locally except `--pull`, which downloads missing models (it retries
automatically, so a flaky connection is fine - Ollama resumes partial downloads).

Other options:
    --dry-run                 show the plan (models, judge, repos) and exit
    --models A B              only these generator models
    --judge M                 judge model (default: first installed from a preference list)
    --repos DIR [DIR ...]     repos to evaluate (default: every folder in eval_repos/)
    --resume eval_results/X   continue an interrupted run, skipping finished work
    --timeout-min N           per model+repo generation timeout (default 90)
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Generators to compare, best-guess order. Anything not installed is skipped.
CANDIDATES = [
    "qwen2.5-coder:7b",
    "qwen3:8b",
    "qwen2.5-coder:14b",
    "deepseek-coder-v2:16b",
    "phi4:14b",
    "llama3.1:8b",
]
# Judge preference: a model that is not also being judged, strongest first.
JUDGE_PREFERENCE = ["phi4:14b", "llama3.1:8b", "gemma3:12b", "gemma3:4b", "llama3.2:latest", "qwen3:8b"]

SKIP_DIRS = {".git", "venv", ".venv", "__pycache__", "node_modules", "target", "build"}
PLACEHOLDER = "No docstring provided."


# --------------------------------------------------------------------------- ollama

def installed_models() -> List[str]:
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.split()[0] for line in out.splitlines()[1:] if line.strip()]


def pull_models(models: List[str], attempts: int = 8) -> None:
    """`ollama pull` with retries: partial downloads resume, so a bad connection just needs more tries."""
    have = set(installed_models())
    for model in models:
        if model in have:
            continue
        for attempt in range(1, attempts + 1):
            print(f"\n[pull] {model} (attempt {attempt}/{attempts})", flush=True)
            if subprocess.run(["ollama", "pull", model]).returncode == 0:
                break
            time.sleep(10)
        else:
            print(f"[pull] giving up on {model}; it will be skipped", flush=True)


def stop_model(model: str) -> None:
    """Unload a model so the next one gets the whole 6 GB GPU."""
    subprocess.run(["ollama", "stop", model], capture_output=True, timeout=60)


# --------------------------------------------------------------------------- config

def write_config(model: str, directory: Path) -> Path:
    # Built here (not via src.web.config_handler) so this script never imports the Flask/eventlet app.
    llm = {
        "type": "huggingface",
        "model": model,
        "api_base": "http://localhost:11434/v1",
        "api_key": "ollama",
        "temperature": 0.1,
        "max_output_tokens": 2048,
        "max_input_tokens": 8000,
    }
    if model.startswith("qwen3"):
        llm["reasoning_effort"] = "none"  # thinking model: skip the slow hidden reasoning
    config = {
        "llm": llm,
        "flow_control": {"max_reader_search_attempts": 2, "max_verifier_rejections": 1, "status_sleep_time": 0},
        "docstring_options": {"overwrite_docstrings": False},
    }
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (re.sub(r"[^A-Za-z0-9]+", "_", model) + ".yaml")
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def make_llm(model: str, directory: Path):
    from src.agent.llm.factory import LLMFactory

    config = LLMFactory.load_config(str(write_config(model, directory)))
    return LLMFactory.create_llm(config["llm"])


# --------------------------------------------------------------------------- repos

def has_files(repo: Path, suffix: str) -> bool:
    return any(p.suffix == suffix and not (set(p.parts) & SKIP_DIRS) for p in repo.rglob(f"*{suffix}"))


def copy_repo(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*SKIP_DIRS))


# --------------------------------------------------------------------------- generation

def generate(model: str, repo: Path, run_dir: Path, work: Path, timeout_min: int) -> Dict:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", model)
    out_dir = run_dir / "outputs" / slug / repo.name
    copy_repo(repo, out_dir)

    config = write_config(model, run_dir / "configs")
    log_path = run_dir / "logs" / f"{slug}__{repo.name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Work in a short temp path (Windows long-path limits) then copy back.
    scratch = work / f"{slug}_{repo.name}"
    copy_repo(repo, scratch)

    cmd = [sys.executable, "generate_docstrings.py", "--repo-path", str(scratch), "--config-path", str(config)]
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
    status, started = "ok", time.time()
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout_min * 60)
        if proc.returncode != 0:
            status = f"exit {proc.returncode}"
    except subprocess.TimeoutExpired:
        status = "timeout"
    seconds = time.time() - started

    copy_repo(scratch, out_dir)
    shutil.rmtree(scratch, ignore_errors=True)

    text = log_path.read_text(encoding="utf-8", errors="replace")
    processed = re.search(r"Total components processed: (\d+)/(\d+)", text)
    return {
        "status": status,
        "seconds": round(seconds, 1),
        "processed": int(processed.group(1)) if processed else text.count("Successfully updated"),
        "total": int(processed.group(2)) if processed else None,
        "updated": text.count("Successfully updated"),
        "format_warnings": text.count("no DOCSTRING XML tags"),
        "errors": len(re.findall(r"Error generating|No docstring generated|Traceback", text)),
        "out_dir": str(out_dir),
    }


# --------------------------------------------------------------------------- completeness

def python_metrics(repo_dir: Path) -> Dict:
    import ast
    from eval_completeness import process_directory

    total = documented = placeholders = 0
    words = []
    for path in repo_dir.rglob("*.py"):
        if set(path.parts) & SKIP_DIRS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                total += 1
                doc = ast.get_docstring(node)
                if doc and doc.strip() == PLACEHOLDER:
                    placeholders += 1
                elif doc:
                    documented += 1
                    words.append(len(doc.split()))
    score = None
    result = process_directory(str(repo_dir))
    if result.get("status") == "success":
        score = result["statistics"]["overall_average_score"]
    return {"components": total, "documented": documented, "placeholders": placeholders,
            "completeness": score, "avg_words": round(sum(words) / len(words), 1) if words else 0}


def java_metrics(repo_dir: Path) -> Dict:
    from src.dependency_analyzer.java_parser import JavaDependencyParser
    from src.dependency_analyzer.javadoc_sanitizer import tag_requirements

    components = JavaDependencyParser(str(repo_dir)).parse_repository()
    scores, words, documented = [], [], 0
    for comp in components.values():
        if not comp.has_docstring:
            scores.append(0.0)
            continue
        documented += 1
        doc = comp.docstring or ""
        words.append(len(doc.split()))
        params, needs_return, _ = tag_requirements(comp.source_code)
        required = len(params) + (1 if needs_return else 0)
        present = sum(1 for p in params if re.search(rf"@param\s+{re.escape(p)}\b", doc))
        present += 1 if needs_return and re.search(r"@return\b", doc) else 0
        scores.append(present / required if required else 1.0)
    return {"components": len(components), "documented": documented, "placeholders": 0,
            "completeness": sum(scores) / len(scores) if scores else None,
            "avg_words": round(sum(words) / len(words), 1) if words else 0}


def measure(out_dir: Path) -> Dict:
    parts = []
    if has_files(out_dir, ".py"):
        parts.append(python_metrics(out_dir))
    if has_files(out_dir, ".java"):
        parts.append(java_metrics(out_dir))
    if not parts:
        return {"components": 0, "documented": 0, "placeholders": 0, "completeness": None, "avg_words": 0}
    scored = [p["completeness"] for p in parts if p["completeness"] is not None]
    return {
        "components": sum(p["components"] for p in parts),
        "documented": sum(p["documented"] for p in parts),
        "placeholders": sum(p["placeholders"] for p in parts),
        "completeness": sum(scored) / len(scored) if scored else None,
        "avg_words": round(sum(p["avg_words"] for p in parts) / len(parts), 1),
    }


# --------------------------------------------------------------------------- truthfulness

def judge_segments(out_dir: Path):
    """Yield (name, language, source segment incl. its doc) for every documented component."""
    from judge_truthfulness import extract_documented_components

    for path in out_dir.rglob("*.py"):
        if set(path.parts) & SKIP_DIRS:
            continue
        try:
            source = path.read_text(encoding="utf-8")
            for name, segment in extract_documented_components(source):
                yield f"{path.name}:{name}", "python", segment
        except (SyntaxError, UnicodeDecodeError):
            continue
    if has_files(out_dir, ".java"):
        from src.dependency_analyzer.java_parser import JavaDependencyParser

        for comp_id, comp in JavaDependencyParser(str(out_dir)).parse_repository().items():
            if comp.has_docstring:
                yield f"{Path(comp.file_path).name}:{comp_id.split('.')[-1]}", "java", f"{comp.docstring}\n{comp.source_code}"


def judge_output(llm, out_dir: Path) -> List[Dict]:
    from judge_truthfulness import SYSTEM_PROMPT, parse_verdict

    rows = []
    for name, language, segment in judge_segments(out_dir):
        system = SYSTEM_PROMPT if language == "python" else SYSTEM_PROMPT.replace("Python docstrings", "Java Javadoc comments")
        messages = [llm.format_message("system", system),
                    llm.format_message("user", f"Component: {name}\n\n```{language}\n{segment}\n```")]
        try:
            response = llm.generate(messages=messages, temperature=0.0, max_tokens=2048)
        except Exception as exc:  # a hung/failed judge call should not abort the whole run
            rows.append({"component": name, "verdict": "ERROR", "issues": str(exc)[:200]})
            continue
        verdict, issues = parse_verdict(response)
        rows.append({"component": name, "verdict": verdict, "issues": issues.replace("\n", " | ")})
    return rows


def truthfulness(rows: List[Dict]) -> Dict:
    weight = {"TRUTHFUL": 1.0, "PARTIALLY_TRUTHFUL": 0.5, "HALLUCINATED": 0.0}
    scored = [weight[r["verdict"]] for r in rows if r["verdict"] in weight]
    return {
        "judged": len(scored),
        "unparseable": sum(1 for r in rows if r["verdict"] not in weight),
        "hallucinated": sum(1 for r in rows if r["verdict"] == "HALLUCINATED"),
        "truthfulness": sum(scored) / len(scored) if scored else None,
    }


# --------------------------------------------------------------------------- driver

def pick_judges(installed: List[str], requested: Optional[str]):
    primary = requested or next((m for m in JUDGE_PREFERENCE if m in installed), None)
    fallback = next((m for m in JUDGE_PREFERENCE if m in installed and m != primary), None)
    return primary, fallback


def pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pull", action="store_true", help="download missing candidate models first (retries on failure)")
    parser.add_argument("--models", nargs="+", help="generator models (default: every installed candidate)")
    parser.add_argument("--judge", help="judge model (default: first installed from the preference list)")
    parser.add_argument("--repos", nargs="+", help="repo folders (default: all folders in eval_repos/)")
    parser.add_argument("--resume", help="existing eval_results/<run> directory to continue")
    parser.add_argument("--timeout-min", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.pull:
        wanted = list(args.models or CANDIDATES)
        if not args.judge and not any(m in installed_models() for m in JUDGE_PREFERENCE[:3]):
            wanted.append(JUDGE_PREFERENCE[0])
        pull_models(wanted)

    installed = installed_models()
    if not installed:
        sys.exit("No Ollama models found. Is Ollama running? Try: ollama list")

    generators = [m for m in (args.models or CANDIDATES) if m in installed]
    missing = [m for m in (args.models or CANDIDATES) if m not in installed]
    judge, fallback = pick_judges(installed, args.judge)
    repos = [Path(r).resolve() for r in args.repos] if args.repos else sorted(
        p for p in (ROOT / "eval_repos").glob("*") if p.is_dir())
    if not generators or not repos:
        sys.exit(f"Nothing to do: generators={generators}, repos={[r.name for r in repos]}")

    print("Generators :", ", ".join(generators))
    if missing:
        print("Not installed (skipped; use --pull):", ", ".join(missing))
    print("Judge      :", judge, f"(fallback for its own output: {fallback})" if fallback else "(no fallback available)")
    print("Repos      :", ", ".join(r.name for r in repos))
    if args.dry_run:
        return

    run_dir = Path(args.resume) if args.resume else ROOT / "eval_results" / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "results.json"
    state: Dict[str, Dict] = json.loads(state_path.read_text()) if state_path.exists() else {}
    work = Path(tempfile.gettempdir()) / "da_eval"
    work.mkdir(parents=True, exist_ok=True)

    def save():
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Phase 1: generation, one model at a time so each gets the whole GPU.
    for model in generators:
        for repo in repos:
            key = f"{model}|{repo.name}"
            if state.get(key, {}).get("generation", {}).get("status") == "ok":
                print(f"[skip] {key} already generated")
                continue
            print(f"\n[generate] {model} on {repo.name} ...", flush=True)
            gen = generate(model, repo, run_dir, work, args.timeout_min)
            print(f"           {gen['status']} in {gen['seconds']}s, {gen['processed']}/{gen['total']} components, "
                  f"{gen['format_warnings']} format warnings", flush=True)
            state[key] = {"model": model, "repo": repo.name, "generation": gen,
                          "quality": measure(Path(gen["out_dir"]))}
            save()
        stop_model(model)

    # Phase 2: truthfulness judging, one judge model at a time.
    judgements: List[Dict] = []
    jobs = {}
    for key, entry in state.items():
        who = fallback if entry["model"] == judge else judge
        jobs.setdefault(who, []).append(key)
    for who, keys in jobs.items():
        if who is None:
            continue
        llm = make_llm(who, run_dir / "configs")
        for key in keys:
            entry = state[key]
            if "truth" in entry:
                continue
            print(f"\n[judge] {who} judging {key} ...", flush=True)
            rows = judge_output(llm, Path(entry["generation"]["out_dir"]))
            entry["truth"] = {**truthfulness(rows), "judge": who, "rows": rows}
            save()
        stop_model(who)

    # Phase 3: report.
    per_model: Dict[str, Dict] = {}
    for key, entry in state.items():
        agg = per_model.setdefault(entry["model"], {"sec": 0.0, "comps": 0, "ok": 0, "total": 0, "warn": 0,
                                                   "errors": 0, "comp_scores": [], "truth": [], "halluc": 0,
                                                   "judged": 0, "judges": set(), "status": set()})
        gen, quality, truth = entry["generation"], entry["quality"], entry.get("truth", {})
        agg["sec"] += gen["seconds"]
        agg["comps"] += gen["processed"] or 0
        agg["ok"] += gen["updated"]
        agg["total"] += gen["total"] or quality["components"]
        agg["warn"] += gen["format_warnings"]
        agg["errors"] += gen["errors"]
        agg["status"].add(gen["status"])
        if quality["completeness"] is not None:
            agg["comp_scores"].append(quality["completeness"])
        if truth.get("truthfulness") is not None:
            agg["truth"].append((truth["truthfulness"], truth["judged"]))
            agg["halluc"] += truth["hallucinated"]
            agg["judged"] += truth["judged"]
        if truth.get("judge"):
            agg["judges"].add(truth["judge"])
        for row in truth.get("rows", []):
            judgements.append({"model": entry["model"], "repo": entry["repo"], **row})

    header = ["Model", "Components done", "Sec/component", "Format warnings", "Completeness", "Truthfulness",
              "Hallucinated", "Judge", "Status"]
    table = []
    for model, a in per_model.items():
        weighted = sum(s * n for s, n in a["truth"]) / sum(n for _, n in a["truth"]) if a["truth"] else None
        comp = sum(a["comp_scores"]) / len(a["comp_scores"]) if a["comp_scores"] else None
        judges = ", ".join(sorted(a["judges"])) + ("*" if model == judge else "")
        table.append([model, f"{a['ok']}/{a['total']}", f"{a['sec'] / a['comps']:.0f}s" if a["comps"] else "n/a",
                      a["warn"], pct(comp), pct(weighted), f"{a['halluc']}/{a['judged']}", judges,
                      "ok" if a["status"] == {"ok"} else "/".join(sorted(a["status"]))])

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in table]
    notes = ("\n\n`*` = this model was also the primary judge, so a different model judged its output; "
             "judges differ, so compare truthfulness across rows with care.\n"
             "Completeness = share of required sections/tags present. Truthfulness = (TRUTHFUL + 0.5 x PARTIAL) / judged.")
    summary = "\n".join(lines) + notes
    (run_dir / "summary.md").write_text(summary + "\n", encoding="utf-8")
    with open(run_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(table)
    with open(run_dir / "judgements.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "repo", "component", "verdict", "issues"])
        writer.writeheader()
        writer.writerows(judgements)

    print("\n" + summary)
    print(f"\nFull results: {run_dir}")


if __name__ == "__main__":
    main()
