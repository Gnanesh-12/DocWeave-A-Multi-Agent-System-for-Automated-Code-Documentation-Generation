# Copyright (c) Meta Platforms, Inc. and affiliates
"""
Configuration handler for the docstring generation web interface.

This module handles reading, writing, and validating the configuration for
the docstring generation process.
"""

import os
import yaml
import json
import tempfile
from pathlib import Path

# Local Ollama models supported by the paste-a-link UI, matching the setups
# compared by compare_models.py (see config/agent_config_*.yaml for the first three).
OLLAMA_MODELS = [
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "qwen3:8b",
    "deepseek-coder-v2:16b",
    "phi4:14b",
    "llama3.1:8b",
    "llama3.2:latest",
    "codellama:13b-instruct",
]


# Hosted Claude models (Anthropic API). Offered only when ANTHROPIC_API_KEY is set in the
# environment the web server was started from; the key itself is never written to a config.
CLAUDE_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5-5",
]
CLAUDE_KEY_ENV = "ANTHROPIC_API_KEY"


def is_claude_model(model: str) -> bool:
    return model in CLAUDE_MODELS


def claude_available() -> bool:
    return bool(os.environ.get(CLAUDE_KEY_ENV, "").strip())


def installed_ollama_models():
    """Models the UI can actually run: installed Ollama models, plus Claude when a key is set.

    Falls back to the full Ollama list if the `ollama` CLI cannot be queried, so a missing CLI
    never leaves the dropdown empty.
    """
    import subprocess
    models = list(OLLAMA_MODELS)
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15).stdout
        installed = {line.split()[0] for line in out.splitlines()[1:] if line.strip()}
        models = [m for m in OLLAMA_MODELS if m in installed] or models
    except (OSError, subprocess.TimeoutExpired):
        pass
    if claude_available():
        models += CLAUDE_MODELS
    return models


def build_claude_config(model: str):
    """Agent config for a hosted Claude model. The API key stays a placeholder resolved from the
    environment at start-up, so no secret is saved to the temporary config file."""
    return {
        "llm": {
            "type": "claude",
            "model": model,
            "api_key": "${%s}" % CLAUDE_KEY_ENV,
            "temperature": 0.1,
            "max_output_tokens": 2048,
            "rate_limits": {
                "requests_per_minute": 50,
                "input_tokens_per_minute": 40000,
                "output_tokens_per_minute": 16000,
                "input_token_price_per_million": 1.0 if "haiku" in model else 3.0,
                "output_token_price_per_million": 5.0 if "haiku" in model else 15.0,
            },
        },
        "flow_control": {
            "max_reader_search_attempts": 2,
            "max_verifier_rejections": 1,
            "status_sleep_time": 0,
        },
        "docstring_options": {
            "overwrite_docstrings": False,
        },
    }


def build_ollama_config(model: str):
    """
    Build a full agent config dict for a local Ollama model.

    Args:
        model: One of OLLAMA_MODELS

    Returns:
        Dictionary containing the configuration, in the same shape as
        config/agent_config_qwen.yaml

    Raises:
        ValueError: If the model is not one of the supported OLLAMA_MODELS
    """
    if is_claude_model(model):
        if not claude_available():
            raise ValueError(
                f"{CLAUDE_KEY_ENV} is not set. In the terminal you start the web server from, run: "
                f'$env:{CLAUDE_KEY_ENV} = "<your key>", then restart the server.'
            )
        return build_claude_config(model)
    if model not in OLLAMA_MODELS:
        raise ValueError(f"Unsupported model: {model}. Supported models: {OLLAMA_MODELS + CLAUDE_MODELS}")

    llm = {
        "type": "huggingface",
        "model": model,
        "api_base": "http://localhost:11434/v1",
        "api_key": "ollama",
        "temperature": 0.1,
        "max_output_tokens": 4096,
        "max_input_tokens": 8000,
    }
    if model.startswith("qwen3"):
        # Thinking model: skip the slow hidden reasoning pass.
        llm["reasoning_effort"] = "none"

    return {
        "llm": llm,
        "flow_control": {
            "max_reader_search_attempts": 2,
            "max_verifier_rejections": 1,
            "status_sleep_time": 0,
        },
        "docstring_options": {
            "overwrite_docstrings": False,
        },
    }

def get_default_config():
    """
    Get the default configuration from agent_config.yaml.
    
    Returns:
        Dictionary containing the default configuration
    """
    default_config_path = Path('config/agent_config.yaml')
    
    if not default_config_path.exists():
        return {
            'llm': {
                'type': 'claude',
                'api_key': '',
                'model': 'claude-3-5-haiku-latest',
                'temperature': 0.1,
                'max_tokens': 4096
            },
            'flow_control': {
                'max_reader_search_attempts': 2,
                'max_verifier_rejections': 1,
                'status_sleep_time': 1
            },
            'docstring_options': {
                'overwrite_docstrings': False
            }
        }
    
    with open(default_config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config

def validate_config(config):
    """
    Validate that the configuration has the required fields.
    
    Args:
        config: Dictionary containing the configuration to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_keys = ['llm', 'flow_control', 'docstring_options']
    
    for key in required_keys:
        if key not in config:
            return False, f"Missing required configuration section: {key}"
    
    # Check specific required fields in llm section
    llm_required = ['type', 'api_key', 'model']
    for key in llm_required:
        if key not in config['llm']:
            return False, f"Missing required field in llm section: {key}"
    
    return True, ""

def save_config(config):
    """
    Save the configuration to a temporary file for use by the generation process.
    
    Args:
        config: Dictionary containing the configuration to save
        
    Returns:
        Path to the saved configuration file
    """
    # Validate configuration
    is_valid, error_message = validate_config(config)
    if not is_valid:
        raise ValueError(f"Invalid configuration: {error_message}")
    
    # Create a temporary file
    temp_dir = tempfile.gettempdir()
    config_file = os.path.join(temp_dir, 'docstring_generator_config.yaml')
    
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    return config_file 