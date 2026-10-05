# Copyright (c) Meta Platforms, Inc. and affiliates
from importlib import import_module

from .base import BaseLLM
from .factory import LLMFactory

# Provider classes load on first access so a local-only run never imports (or
# prints warnings from) the OpenAI, Anthropic or Google SDKs it does not use.
_PROVIDERS = {
    'OpenAILLM': '.openai_llm',
    'ClaudeLLM': '.claude_llm',
    'HuggingFaceLLM': '.huggingface_llm',
    'GeminiLLM': '.gemini_llm',
}

__all__ = ['BaseLLM', 'LLMFactory', *_PROVIDERS]


def __getattr__(name):
    if name in _PROVIDERS:
        return getattr(import_module(_PROVIDERS[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
