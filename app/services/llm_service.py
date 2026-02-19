"""
Centralized LLM Service — single place to manage & switch providers at runtime.

Usage in any service:
    from app.services.llm_service import llm_service

    text = llm_service.generate("Tell me a joke")
    info = llm_service.info()
    llm_service.switch_provider("gemini")   # hot-swap, no restart
"""

import logging
from threading import Lock
from typing import Literal

from app.config import settings
from app.services.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

ProviderType = Literal["ollama", "gemini"]

SUPPORTED_PROVIDERS: list[str] = ["ollama", "gemini"]


def _create_provider(name: str) -> BaseLLMProvider:
    """Lazy-import and instantiate a provider by name."""
    if name == "ollama":
        from app.services.llm_providers.ollama_provider import OllamaProvider
        return OllamaProvider()
    elif name == "gemini":
        from app.services.llm_providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{name}'. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )


class LLMService:
    """
    Thread-safe singleton that wraps the active LLM provider.

    Every service that needs AI just calls:
        llm_service.generate(prompt, **opts)

    To switch at runtime (no restart):
        llm_service.switch_provider("gemini")
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._provider: BaseLLMProvider = _create_provider(settings.llm_provider)
        self._provider_name: str = settings.llm_provider
        logger.info(
            "LLMService initialised with provider: %s", self._provider.provider_name
        )

    # ------------------------------------------------------------------
    # Core API (delegates to the active provider)
    # ------------------------------------------------------------------

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using the current LLM provider."""
        return self._provider.generate(prompt, **kwargs)

    def check_availability(self) -> bool:
        """Check whether the current provider is reachable."""
        try:
            return self._provider.check_availability()
        except Exception as e:
            logger.error("Provider %s availability check failed: %s", self.provider_name, e)
            return False

    # ------------------------------------------------------------------
    # Provider info
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def active_provider_key(self) -> str:
        """The config key (ollama / gemini) of the current provider."""
        return self._provider_name

    def info(self) -> dict:
        """Return provider metadata (useful for health / debug endpoints)."""
        return {
            "active_provider": self._provider_name,
            "provider_display": self._provider.provider_name,
            "supported_providers": SUPPORTED_PROVIDERS,
        }

    # ------------------------------------------------------------------
    # Runtime switching
    # ------------------------------------------------------------------

    def switch_provider(self, name: str) -> dict:
        """
        Hot-swap the active LLM provider.

        Returns a dict with old/new provider info.
        Raises ValueError for unknown providers.
        """
        name = name.strip().lower()
        if name not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unknown provider '{name}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
            )

        with self._lock:
            old_name = self._provider_name
            if name == old_name:
                logger.info("Provider already set to %s — no change", name)
                return {"changed": False, "provider": name}

            logger.info("Switching LLM provider: %s → %s", old_name, name)
            self._provider = _create_provider(name)
            self._provider_name = name
            logger.info("LLM provider switched to %s", self._provider.provider_name)

            return {
                "changed": True,
                "old_provider": old_name,
                "new_provider": name,
            }


# ── Singleton ────────────────────────────────────────────────────────
llm_service = LLMService()
