"""
LLM Provider Factory.

Responsible for instantiating the correct LLM provider class based on the configuration.
Flow: Called by LLMService during initialization or when hot-swapping providers.
It reads the provider name and creates the matching concrete implementation.
"""

import logging
from typing import Literal

from app.config import settings
from app.services.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

LLMProviderType = Literal["ollama", "gemini"]


def get_llm_provider(provider_type: LLMProviderType | None = None) -> BaseLLMProvider:
    """
    Factory function to get the appropriate LLM provider.
    
    Args:
        provider_type: Type of provider to create. If None, uses settings.llm_provider
        
    Returns:
        BaseLLMProvider: Instantiated LLM provider
        
    Raises:
        ValueError: If provider_type is not supported
    """
    if provider_type is None:
        provider_type = settings.llm_provider
    
    logger.info("Initializing LLM provider: %s", provider_type)
    
    # Lazy imports - only import the provider that's actually being used
    if provider_type == "ollama":
        from app.services.llm_providers.ollama_provider import OllamaProvider
        return OllamaProvider()
    elif provider_type == "gemini":
        from app.services.llm_providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider_type}. "
            f"Supported providers: ollama, gemini"
        )
