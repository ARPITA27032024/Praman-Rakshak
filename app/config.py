import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""
    
    APP_NAME: str = "Kybernetes Digital Evidence Management System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Storage paths
    STORAGE_DIR: str = "./storage"
    ORIGINALS_DIR: str = "./storage/originals"
    REDACTED_DIR: str = "./storage/redacted"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
