"""Provider-agnostic AI client. Sends a chat completion to the configured
OpenAI-compatible backend and returns parsed JSON to the caller."""

import json
import logging

from dealcourier.ai.providers import get_provider
from dealcourier.config import get_config

logger = logging.getLogger("dealcourier.ai.client")


def single_message(
    system: str,
    user_content: str,
    model: str | None = None,
    max_tokens: int | None = None,
) -> dict | None:
    """Send a single chat completion and return the parsed JSON response.

    `model` defaults to `cfg.default_model` when not supplied. Pass a different
    model id (e.g. `cfg.terms_model`) to route a specific call to another model
    on the same backend.
    """
    cfg = get_config()
    chosen_model = model or cfg.default_model
    max_tokens = max_tokens or cfg.ai_max_tokens

    text = get_provider().complete(
        system=system,
        user_content=user_content,
        model=chosen_model,
        max_tokens=max_tokens,
    )

    if text is None:
        return None

    return _extract_json(text)


def _extract_json(text: str) -> dict | None:
    """Parse JSON from a text response. Tolerates markdown code fences."""
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # ```json ... ```
    if "```json" in text:
        try:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return json.loads(text[start:end].strip())
        except (ValueError, json.JSONDecodeError):
            pass

    # ``` ... ```
    if "```" in text:
        try:
            start = text.index("```") + 3
            end = text.index("```", start)
            return json.loads(text[start:end].strip())
        except (ValueError, json.JSONDecodeError):
            pass

    # First { to last } fallback — helps with verbose models
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except json.JSONDecodeError:
            pass

    logger.warning(f"Response is not valid JSON: {text[:200]}")
    return None
