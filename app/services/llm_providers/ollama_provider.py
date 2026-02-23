"""
Ollama LLM Provider.

Implements the BaseLLMProvider interface for local Ollama models.
Flow: Receives prompts from LLMService, sends them to the local Ollama instance
via its REST API, and returns the text response.
"""

import logging
from ollama import Client

from app.config import settings
from app.services.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider implementation."""

    def __init__(self):
        """Initialize Ollama provider."""
        self.client = Client(host=settings.ollama_host)
        self.model = settings.ollama_model
        logger.info("Initialized Ollama provider with model: %s", self.model)

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Ollama.
        
        Args:
            prompt: The prompt to send to Ollama
            **kwargs: Options like temperature, num_predict, top_p
            
        Returns:
            str: Generated text response
        """
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options=kwargs,
            )
            return response.response
        except Exception as e:
            logger.error("Ollama generation error: %s", e)
            raise

    def check_availability(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            models = self.client.list()
            model_names = [m.model for m in models.models]
            available = any(self.model in name for name in model_names)
            if available:
                logger.info("Ollama is available with model: %s", self.model)
            else:
                logger.warning("Ollama model %s not found", self.model)
            return available
        except Exception as e:
            logger.error("Ollama not available: %s", e)
            return False

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "Ollama"
