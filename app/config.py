"""
Application Configuration

Loads environment variables and provides configuration settings for the
entire application, including database connections, LLM providers, and server setup.
Services and repositories use these settings to connect to external systems.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "ivas"
    app_env: str = "development"
    app_debug: bool = True

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 9999

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "learn_go_db"
    db_ssl_mode: str = "disable"
    db_pool_size: int = 25
    db_max_overflow: int = 25
    db_pool_timeout: int = 30

    # LLM Provider Selection
    llm_provider: str = "ollama"  # Options: "ollama" or "gemini"

    # Ollama / AI
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout: int = 300

    # Gemini / AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"  # Options: gemini-2.0-flash, gemini-2.0-flash-lite, gemini-2.5-pro-preview-06-05
    gemini_live_model: str = "gemini-2.5-flash-native-audio-latest"  # Model for Gemini Live API (real-time voice)

    # TTS (Text-to-Speech)
    tts_provider: str = "openai"  # Options: "openai" or "edge"
    openai_api_key: str = ""
    openai_tts_model: str = "tts-1-hd"  # "tts-1" (fast) or "tts-1-hd" (high quality)
    openai_tts_voice: str = "nova"  # alloy, echo, fable, onyx, nova, shimmer

    # Logging
    log_level: str = "debug"
    log_format: str = "text"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
