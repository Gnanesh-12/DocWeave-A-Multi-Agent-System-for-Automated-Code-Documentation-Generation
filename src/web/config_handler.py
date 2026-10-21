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

# Groq (OpenAI-compatible, has a free tier). Offered when GROQ_API_KEY is set. Model ids can be changed
# without code via DOCWEAVE_GROQ_MODELS (comma separated), in case Groq retires one.
GROQ_KEY_ENV = "GROQ_API_KEY"
GROQ_API_BASE = os.environ.get("DOCWEAVE_GROQ_API_BASE", "https://api.groq.com/openai/v1")  # override for other OpenAI-compatible hosts
GROQ_PREFIX = "groq:"


# Groq retires models regularly (llama-3.3-70b-versatile was shut down in August 2026), so the model list is
# discovered from Groq itself instead of being hard-coded. Preferred models are listed first.
GROQ_PREFERRED = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
]
GROQ_FALLBACK = ["openai/gpt-oss-120b"]
# Not chat/text models, or agent systems rather than plain models.
_GROQ_EXCLUDE = ("whisper", "guard", "tts", "orpheus", "playai", "embed", "safeguard", "compound", "prompt-guard")
_groq_cache = {"at": 0.0, "ids": []}


def groq_model_ids():
    """Chat models the Groq key can use. DOCWEAVE_GROQ_MODELS (comma separated) overrides discovery.

    Asks Groq's /models endpoint (cached for 5 minutes). If that fails, falls back to a known-good model.
    """
    override = os.environ.get("DOCWEAVE_GROQ_MODELS", "").strip()
    if override:
        return [m.strip() for m in override.split(",") if m.strip()]
    import time
    now = time.time()
    if _groq_cache["ids"] and now - _groq_cache["at"] < 300:
        return list(_groq_cache["ids"])
    ids = []
    try:
        import json
        import urllib.request
        req = urllib.request.Request(
            GROQ_API_BASE.rstrip("/") + "/models",
            headers={"Authorization": "Bearer " + os.environ.get(GROQ_KEY_ENV, "").strip(), "User-Agent": "DocWeave"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            available = [m["id"] for m in json.load(resp).get("data", []) if m.get("active", True)]
        usable = [m for m in available if not any(x in m.lower() for x in _GROQ_EXCLUDE)]
        ids = [m for m in GROQ_PREFERRED if m in usable] + sorted(m for m in usable if m not in GROQ_PREFERRED)
        ids = ids[:8]
    except Exception:
        ids = []
    if ids:
        _groq_cache.update(at=now, ids=ids)
        return list(ids)
    return list(GROQ_FALLBACK)


def is_groq_model(model: str) -> bool:
    return model.startswith(GROQ_PREFIX)


def groq_available() -> bool:
    return bool(os.environ.get(GROQ_KEY_ENV, "").strip())


def hosted_only() -> bool:
    """Cloud deployments have no Ollama/GPU: offer hosted models only."""
    return os.environ.get("DOCWEAVE_HOSTED_ONLY") == "1"


def is_hosted_model(model: str) -> bool:
    return is_claude_model(model) or is_groq_model(model)


def is_claude_model(model: str) -> bool:
    return model in CLAUDE_MODELS


def claude_available() -> bool:
    return bool(os.environ.get(CLAUDE_KEY_ENV, "").strip())


def installed_ollama_models():
    """Models the UI can actually run: installed Ollama models, plus hosted ones whose API key is set.

    Falls back to the full Ollama list if Ollama cannot be queried, so a missing server never leaves
    the dropdown empty. In hosted-only mode (cloud deployment) no local models are offered at all.
    """
    models = [] if hosted_only() else list(OLLAMA_MODELS)
    if not hosted_only():
        # Ask Ollama over HTTP rather than running `ollama list`: the web server runs under eventlet,
        # where a blocking subprocess call inside a request freezes every other request.
        try:
            import json
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as resp:
                installed = {m["name"] for m in json.load(resp).get("models", [])}
            models = [m for m in OLLAMA_MODELS if m in installed] or models
        except Exception:
            pass  # Ollama not reachable: offer the full list so the dropdown is never empty
    if groq_available():
        models += [GROQ_PREFIX + m for m in groq_model_ids()]
    if claude_available():
        models += CLAUDE_MODELS
    return models


def build_groq_config(model: str):
    """Agent config for a Groq-hosted model through the OpenAI-compatible client. The key stays a
    placeholder resolved from the environment, so no secret is written to the temporary config file."""
    model_id = model[len(GROQ_PREFIX):]
    llm = {
        "type": "huggingface",  # the OpenAI-compatible client
        "model": model_id,
        "api_base": GROQ_API_BASE,
        "api_key": "${%s}" % GROQ_KEY_ENV,
        "temperature": 0.1,
        "max_output_tokens": 1024,
        "max_input_tokens": 6000,
        "num_ctx": 0,          # Ollama-only field: do not send it to Groq
        "max_retries": 8,      # free tier is rate limited; retry 429s with the server's Retry-After
    }
    if "gpt-oss" in model_id:
        # Reasoning model: reasoning tokens count against max_tokens, so keep the reasoning short
        # and leave room for the actual docstring.
        llm["reasoning_effort"] = "low"
        llm["max_output_tokens"] = 2048
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
    if is_groq_model(model):
        if not groq_available():
            raise ValueError(f"{GROQ_KEY_ENV} is not set on the server, so Groq models are unavailable.")
        if model[len(GROQ_PREFIX):] not in groq_model_ids():
            raise ValueError(f"Unsupported model: {model}.")
        return build_groq_config(model)
    if is_claude_model(model):
        if not claude_available():
            raise ValueError(
                f"{CLAUDE_KEY_ENV} is not set. In the terminal you start the web server from, run: "
                f'$env:{CLAUDE_KEY_ENV} = "<your key>", then restart the server.'
            )
        return build_claude_config(model)
    if hosted_only() or model not in OLLAMA_MODELS:
        raise ValueError(f"Unsupported model: {model}.")

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