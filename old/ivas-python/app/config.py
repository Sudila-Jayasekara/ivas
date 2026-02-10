from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "IVAS AI Service"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8081
    
    # Ollama configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout: int = 120  # seconds
    
    class Config:
        env_file = ".env"
        env_prefix = "IVAS_AI_"


settings = Settings()
