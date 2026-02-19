"""Google Gemini LLM Provider."""

import logging
from google import genai
from google.genai import types

from app.config import settings
from app.services.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider implementation."""

    def __init__(self):
        """Initialize Gemini provider."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in configuration")

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = settings.gemini_model
        logger.info("Initialized Gemini provider with model: %s", self.model_name)

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Google Gemini.

        Args:
            prompt: The prompt to send to Gemini
            **kwargs: Options like temperature, max_output_tokens, top_p

        Returns:
            str: Generated text response
        """
        try:
            # Map common options to Gemini's format
            config_kwargs = {}
            if "temperature" in kwargs:
                config_kwargs["temperature"] = kwargs["temperature"]
            if "num_predict" in kwargs:
                config_kwargs["max_output_tokens"] = kwargs["num_predict"]
            if "max_output_tokens" in kwargs:
                config_kwargs["max_output_tokens"] = kwargs["max_output_tokens"]
            if "top_p" in kwargs:
                config_kwargs["top_p"] = kwargs["top_p"]

            config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            return response.text
        except Exception as e:
            logger.error("Gemini generation error: %s", e)
            raise

    def check_availability(self) -> bool:
        """Check if Gemini API is configured correctly."""
        try:
            if not settings.gemini_api_key:
                logger.warning("Gemini API key not configured")
                return False

            # Try a simple generation to verify API key works
            test_response = self.client.models.generate_content(
                model=self.model_name,
                contents="Say 'OK' if you can read this.",
            )
            if test_response and test_response.text:
                logger.info("Gemini API is available and working")
                return True
            return False
        except Exception as e:
            logger.error("Gemini not available: %s", e)
            return False

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "Gemini"
