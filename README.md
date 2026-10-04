# DocAgent

<p align="center">
  <img src="assets/meta_logo_white.png" width="20%" alt="Meta Logo">
</p>

## What is DocAgent?

**DocAgent** is an advanced, multi-agent system designed to automatically generate high-quality, context-aware docstrings for Python codebases. By leveraging a hierarchical processing approach, it ensures that even complex dependencies are thoroughly documented.

Current Large Language Models (LLMs) often generate superficial comments that lack broader context. DocAgent solves this by utilizing:
1. **Hierarchical Traversal**: Processes files with fewer dependencies first, building a strong documentation foundation from the bottom up.
2. **Multi-Agent Architecture**: Employs a specialized team of agents (`Reader`, `Searcher`, `Writer`, `Verifier`), coordinated by an `Orchestrator`, to iteratively draft, refine, and verify docstrings.

## Our Local LLM Setup

We have configured this instance of DocAgent to run entirely locally using **Ollama**, completely avoiding the need for expensive API keys and ensuring data privacy. 

We have added support for the following open-weights models:
1. **CodeLlama (13B Instruct)** - Optimized for coding tasks.
2. **Qwen 2.5 Coder (7B)** - Highly capable at reasoning and code generation.

The configurations for these models are located in:
- `config/agent_config_codellama.yaml`
- `config/agent_config_qwen.yaml`

## Quick Start

### 1. Installation

First, install the DocAgent dependencies. We recommend using a virtual environment:

```bash
# Create and activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
# source venv/bin/activate

# Install the package and dependencies
pip install -e .
```

*Note: If you run into dependency conflicts with packages like `protobuf` during installation, make sure to uninstall the conflicting versions and let the `pip install -e .` resolve it.*

### 2. Setup Ollama

Make sure you have [Ollama](https://ollama.com/) installed and running locally. Pull the required models depending on which one you want to use:

```bash
# To use CodeLlama
ollama run codellama:13b-instruct

# To use Qwen 2.5 Coder
ollama run qwen2.5-coder:7b
```

### 3. Usage

You can run the docstring generation by specifying your desired configuration file. 

**Using CodeLlama:**
```bash
python generate_docstrings.py --repo-path <absolute_path_to_your_repo> --config-path config/agent_config_codellama.yaml
```

**Using Qwen 2.5 Coder:**
```bash
python generate_docstrings.py --repo-path <absolute_path_to_your_repo> --config-path config/agent_config_qwen.yaml
```

### 4. Web UI (Optional)

DocAgent includes a web interface for real-time monitoring.
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

## Citation

If you use DocAgent in your research, please cite the [paper](https://arxiv.org/abs/2504.08725):

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

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
