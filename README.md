# DocWeave

<p align="center">
  <img src="assets/meta_logo_white.png" width="20%" alt="Meta Logo">
</p>

## What is DocWeave?

**DocWeave** is an advanced, multi-agent system designed to automatically generate high-quality, context-aware docstrings for Python and Java codebases. By leveraging a hierarchical processing approach, it ensures that even complex dependencies are thoroughly documented.

Current Large Language Models (LLMs) often generate superficial comments that lack broader context. DocWeave solves this by utilizing:
1. **Hierarchical Traversal**: Processes files with fewer dependencies first, building a strong documentation foundation from the bottom up.
2. **Multi-Agent Architecture**: Employs a specialized team of agents (`Reader`, `Searcher`, `Writer`, `Verifier`), coordinated by an `Orchestrator`, to iteratively draft, refine, and verify docstrings.

---

## Supported Local LLMs

We have configured this instance of DocWeave to run entirely locally using **Ollama**, avoiding the need for expensive API keys and ensuring data privacy. 

**Generators (Docstring Writing):**
- `qwen2.5-coder:7b` (Config: `config/agent_config_qwen.yaml`)
- `qwen3:8b` (Config: `config/agent_config_qwen3.yaml`)
- `qwen2.5-coder:14b` 
- `codellama:13b-instruct` (Config: `config/agent_config_codellama.yaml`)
- `deepseek-coder-v2:16b`
- `phi4:14b`
- `llama3.1:8b`

**Judge (Truthfulness Evaluation):**
- `llama3.2:latest` (3B)

You can run `ollama pull <model_name>` to download any of the above models for local use.

---

## 🚀 Quick Start

### 1. Installation

First, clone the repository and install the Python dependencies. We recommend using a virtual environment:

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
*Note: If you run into dependency conflicts with packages like `protobuf` during installation, make sure to uninstall the conflicting versions and let `pip install -e .` resolve it.*

### 2. System Dependencies

**GraphViz (Required for Visualization):**
For visualization components, you need to install system-level GraphViz dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install graphviz graphviz-dev

# CentOS/RHEL
sudo yum install graphviz graphviz-devel

# macOS
brew install graphviz
```

**CUDA Support (Optional):**
If you're using CUDA for accelerated processing, ensure you have the correct CUDA toolkit installed that matches your PyTorch version.

### 3. Start the Web UI (Recommended)

DocWeave includes a modern web interface for real-time monitoring and configuration. The UI allows you to select models, track generation progress, and inspect the dependency graph.

**Start the Backend API:**
```bash
python run_web_ui.py --host 0.0.0.0 --port 5000
```

**Start the Frontend:**
In a new terminal window, run the development server for the React app:
```bash
cd frontend
npm install
npm run dev
```
Then access the UI at the localhost address provided by Vite (typically `http://localhost:5173`).

---

## 💻 CLI Usage

You can also run the docstring generation directly from the command line by specifying your desired configuration file. 

**Using Qwen 3 (8B):**
```bash
python generate_docstrings.py --repo-path <absolute_path_to_your_repo> --config-path config/agent_config_qwen3.yaml
```

**Using CodeLlama:**
```bash
python generate_docstrings.py --repo-path <absolute_path_to_your_repo> --config-path config/agent_config_codellama.yaml
```

---

## 📊 Evaluation

### Truthfulness Evaluation
DocWeave includes a lightweight, free local LLM-judge tool to check if the generated docstrings factually align with the code implementation. It flags hallucinated parameters, exceptions, or incorrect behaviors.

```bash
python judge_truthfulness.py <file1.py> [file2.py ...] --config-path config/agent_config_qwen.yaml
```

### Completeness Evaluation
DocWeave also provides a separate web-based system for evaluating docstring completeness using Abstract Syntax Tree (AST) analysis.

```bash
python src/web_eval/app.py --host 0.0.0.0 --port 5001
```
Access the evaluation UI at `http://localhost:5001`.

---

## Citation

If you use DocWeave in your research, please cite the [paper](https://arxiv.org/abs/2504.08725):

```bibtex
@misc{yang2025docweave,
      title={DocWeave: A Multi-Agent System for Automated Code Documentation Generation}, 
      author={Dayu Yang and Antoine Simoulin and Xin Qian and Xiaoyi Liu and Yuwei Cao and Zhaopu Teng and Grey Yang},
      year={2025},
      eprint={2504.08725},
      archivePrefix={arXiv},
      primaryClass={cs.SE}
}
```