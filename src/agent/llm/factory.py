# Copyright (c) Meta Platforms, Inc. and affiliates
import os
from typing import Dict, Any, Optional
from pathlib import Path
import yaml

from .base import BaseLLM

_DEFAULT_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def resolve_api_key(config: Dict[str, Any], llm_type: str) -> str:
    """API key from the config, or from an environment variable.

    A config value like "${ANTHROPIC_API_KEY}" (or no key at all) is read from the environment,
    so secrets never have to be written into a config file or committed.
    """
    key = str(config.get("api_key") or "").strip()
    env_name = _DEFAULT_KEY_ENV.get(llm_type)
    if key.startswith("${") and key.endswith("}"):
        env_name, key = key[2:-1], ""
    if key:
        return key
    value = os.environ.get(env_name or "", "").strip()
    if not value:
        raise ValueError(
            f"No API key for '{llm_type}'. Set the {env_name} environment variable "
            f"(PowerShell: $env:{env_name} = \"...\") and start the app from that same terminal."
        )
    return value


class LLMFactory:
    """Factory class for creating LLM instances."""
    
    @staticmethod
    def create_llm(config: Dict[str, Any]) -> BaseLLM:
        """Create an LLM instance based on configuration.
        
        Args:
            config: Configuration dictionary containing LLM settings
            
        Returns:
            An instance of BaseLLM
            
        Raises:
            ValueError: If the LLM type is not supported
        """
        llm_type = config["type"].lower()
        model = config.get("model")
        
        if not model:
            raise ValueError("Model must be specified in the config file")
        
        # Extract rate limit settings from config
        # First check if there are specific rate limits in the LLM config
        rate_limits = config.get("rate_limits", {})
        
        # If not, check if there are global rate limits for this provider type
        global_config = LLMFactory.load_config()
        if not rate_limits and "rate_limits" in global_config:
            # Map LLM types to provider names in rate_limits section
            provider_map = {
                "openai": "openai",
                "claude": "claude",
                "gemini": "gemini"
            }
            provider_key = provider_map.get(llm_type, llm_type)
            provider_limits = global_config.get("rate_limits", {}).get(provider_key, {})
            if provider_limits:
                rate_limits = provider_limits
        
        # Providers are imported only when selected, so a local (Ollama) run never
        # loads or contacts the hosted-API SDKs.
        if llm_type == "openai":
            from .openai_llm import OpenAILLM
            return OpenAILLM(
                api_key=resolve_api_key(config, "openai"),
                model=model,
                rate_limits=rate_limits
            )
        elif llm_type == "claude":
            from .claude_llm import ClaudeLLM
            return ClaudeLLM(
                api_key=resolve_api_key(config, "claude"),
                model=model,
                rate_limits=rate_limits
            )
        elif llm_type == "gemini":
            from .gemini_llm import GeminiLLM
            return GeminiLLM(
                api_key=resolve_api_key(config, "gemini"),
                model=model,
                rate_limits=rate_limits
            )
        elif llm_type == "huggingface":
            from .huggingface_llm import HuggingFaceLLM
            return HuggingFaceLLM(
                model_name=model,
                api_base=config.get("api_base", "http://localhost:8000/v1"),
                api_key=config.get("api_key", "EMPTY"),
                device=config.get("device", "cuda"),
                torch_dtype=config.get("torch_dtype", "float16"),
                max_input_tokens=config.get("max_input_tokens", 10000),
                num_ctx=config.get("num_ctx", 8192),
                reasoning_effort=config.get("reasoning_effort")
            )
        else:
            raise ValueError(f"Unsupported LLM type: {llm_type}")
    
    @staticmethod
    def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load LLM configuration from file.
        
        Args:
            config_path: Path to the configuration file. If None, uses default path.
            
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
        """
        if config_path is None:
            config_path = str(Path(__file__).parent.parent.parent.parent / "config" / "agent_config.yaml")
        
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        return config 