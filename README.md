# DocAgent

<p align="center">
  <img src="assets/meta_logo_white.png" width="20%" alt="Meta Logo">
</p>

**DocAgent** is an advanced, multi-agent system designed to automatically generate high-quality, context-aware docstrings for Python codebases. By leveraging a hierarchical processing approach, it ensures that even complex dependencies are thoroughly documented.

## Overview

High-quality documentation is essential for code maintainability. Current Large Language Models (LLMs) often generate superficial comments that lack broader context. DocAgent solves this by utilizing:
1. **Hierarchical Traversal**: Processes files with fewer dependencies first, building a strong documentation foundation from the bottom up.
2. **Multi-Agent Architecture**: Employs a specialized team of agents (`Reader`, `Searcher`, `Writer`, `Verifier`), coordinated by an `Orchestrator`, to iteratively draft, refine, and verify docstrings.

## Citation

If you use DocAgent in your research, please cite our [paper](https://arxiv.org/abs/2504.08725):

```bibtex
@misc{yang2025docagent,
      title={DocAgent: A Multi-Agent System for Automated Code Documentation Generation}, 
      author={Dayu Yang and Antoine Simoulin and Xin Qian and Xiaoyi Liu and Yuwei Cao and Zhaopu Teng and Grey Yang},
      year={2025},
      eprint={2504.08725},
      archivePrefix={arXiv},
      primaryClass={cs.SE}
}
```

## Quick Start

### Installation

```bash
git clone <repository_url>
cd DocAgent
python -m venv venv
source venv/bin/activate
pip install -e .
```

*Note: For optional features, install extras as needed (e.g., `pip install -e ".[dev,web]"`).*

### Configuration

Create your configuration file by copying the provided example:
```bash
cp config/example_config.yaml config/agent_config.yaml
```
Edit `config/agent_config.yaml` to set your LLM provider, API keys, and model preferences. To use a local LLM (e.g., via `vllm`), point the API endpoint in the configuration to your local server.

### Usage

**Command Line Interface (CLI):**
```bash
python generate_docstrings.py --repo-path <absolute_path_to_your_repo>
```

**Web UI:**
DocAgent includes a web interface for real-time monitoring and configuration.
```bash
python run_web_ui.py --host 0.0.0.0 --port 5000
```
Access the UI at `http://localhost:5000`.

## Evaluation

DocAgent provides a separate web-based system for evaluating docstring completeness using Abstract Syntax Tree (AST) analysis.

```bash
python src/web_eval/app.py --host 0.0.0.0 --port 5001
```
Access the evaluation UI at `http://localhost:5001`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
