"""Provider interface. All AI backends must implement complete()."""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Abstract AI provider. Returns raw text; JSON parsing is caller's job."""

    name: str = "base"

    @abstractmethod
    def complete(
        self,
        system: str,
        user_content: str,
        model: str,
        max_tokens: int,
    ) -> str | None:
        """Send a completion request. Return the raw text response or None on failure."""
        raise NotImplementedError
