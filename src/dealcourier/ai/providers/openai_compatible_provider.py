"""Unified OpenAI-compatible chat completions provider.

DealCourier no longer cares which vendor you use. Any endpoint that speaks the
OpenAI Chat Completions schema works here, including:

  - OpenAI            -> https://api.openai.com/v1
  - OpenRouter        -> https://openrouter.ai/api/v1   (use model ids like "z-ai/glm-5.2")
  - DeepSeek          -> https://api.deepseek.com/v1
  - Together / Groq / Fireworks / local vLLM / Ollama's OpenAI shim / etc.

Point `base_url` and `api_key` in config.yaml at your provider, pick the
`default_model` / `terms_model` ids that provider understands, and you're done.
"""

import logging

import httpx

from dealcourier.ai.providers.base import BaseProvider

logger = logging.getLogger("dealcourier.ai.providers.openai_compatible")


class OpenAICompatibleProvider(BaseProvider):
    """Single provider that targets any OpenAI-compatible /chat/completions endpoint."""

    name = "openai_compatible"

    def __init__(self, api_key: str, base_url: str, timeout: int = 60):
        self._api_key = (api_key or "").strip()
        # Normalise: strip trailing slash so we can append "/chat/completions"
        self._base_url = (base_url or "").rstrip("/")
        self._timeout = timeout

        if not self._api_key:
            logger.warning("No api_key configured -- AI calls will fail until one is set")
        if not self._base_url:
            logger.warning("No base_url configured -- AI calls will fail until one is set")

    def complete(self, system: str, user_content: str, model: str, max_tokens: int) -> str | None:
        if not self._api_key:
            logger.error("api_key not configured")
            return None
        if not self._base_url:
            logger.error("base_url not configured")
            return None
        if not model:
            logger.error("No model specified and no default_model configured")
            return None

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        # Ask for JSON output when the prompt clearly expects JSON. Most OpenAI-
        # compatible backends honour response_format={"type":"json_object"}; the
        # ones that don't simply ignore the field, so it's safe to send always.
        wants_json = "JSON" in (system or "") or "JSON" in (user_content or "")
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        if wants_json:
            body["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(
                f"AI request to {url} failed: HTTP {e.response.status_code}: "
                f"{e.response.text[:300]}"
            )
            return None
        except (KeyError, IndexError) as e:
            logger.error(f"Malformed response from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling {url}: {e}")
            return None
