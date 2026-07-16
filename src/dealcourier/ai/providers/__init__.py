"""AI provider abstraction.

DealCourier uses a single OpenAI-compatible backend. Point `base_url` and
`api_key` in config.yaml at any vendor that speaks the OpenAI Chat Completions
schema (OpenAI, OpenRouter, DeepSeek, Groq, Together, vLLM, Ollama, ...).
"""

from dealcourier.ai.providers.base import BaseProvider
from dealcourier.ai.providers.openai_compatible_provider import OpenAICompatibleProvider

__all__ = ["BaseProvider", "get_provider", "reset_provider"]

_provider: OpenAICompatibleProvider | None = None


def get_provider() -> OpenAICompatibleProvider:
    """Return the configured OpenAI-compatible provider (cached)."""
    global _provider
    if _provider is None:
        from dealcourier.config import get_config

        cfg = get_config()
        _provider = OpenAICompatibleProvider(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=cfg.ai_request_timeout_seconds,
        )
    return _provider


def reset_provider() -> None:
    """Clear the cached provider. Call after config changes at runtime."""
    global _provider
    _provider = None
