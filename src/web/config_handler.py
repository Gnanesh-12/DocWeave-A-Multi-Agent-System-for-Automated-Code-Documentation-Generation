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


def installed_ollama_models():
    """Supported models that are actually installed (so the UI never offers one that would fail).

    Falls back to the full supported list if the `ollama` CLI cannot be queried.
    """
    return list(OLLAMA_MODELS)

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
    if model not in OLLAMA_MODELS:
        raise ValueError(f"Unsupported model: {model}. Supported models: {OLLAMA_MODELS}")

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