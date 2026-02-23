"""
Base LLM Provider Interface.

Defines the contract that all concrete LLM providers (e.g., Ollama, Gemini) must implement.
Flow: The factory creates an instance of a provider, and the LLMService delegates
generation requests to that instance via this interface.
"""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)
            
        Returns:
            str: Generated text response
        """
        pass

    @abstractmethod
    def check_availability(self) -> bool:
        """
        Check if the LLM provider is available and configured correctly.
        
        Returns:
            bool: True if provider is available, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider."""
        pass
