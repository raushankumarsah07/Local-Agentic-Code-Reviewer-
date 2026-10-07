"""
Configuration settings for the application.
Reads environment variables from .env file or system environment using Pydantic Settings.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings schema.
    All variables can be overridden using environment variables or a .env file.
    """
    # Application Info
    APP_NAME: str = "Local Agentic Code Reviewer and Architecture Grapher"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Configuration
    # Accepts JSON list string, comma-separated string, or list of strings
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Storage and File Processing Limits
    WORKSPACE_DIR: Path = Field(default=Path("workspace"))
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, description="Max allowed ZIP file upload size in Megabytes")
    MAX_FILE_COUNT: int = Field(default=5000, description="Max total files allowed inside uploaded ZIP archive")

    # Database Configuration (SQLite by default, switchable to Postgres via connection string)
    DATABASE_URL: str = "sqlite:///./app_data/app.db"

    # ChromaDB Vector Store
    CHROMA_PERSIST_DIR: Path = Field(default=Path("./chroma_db"))

    # Local Ollama LLM & Embedding Settings (Never hardcoded)
    LLM_MODEL: str = Field(default="llama3.2", description="Ollama LLM model name")
    EMBEDDING_MODEL: str = Field(default="nomic-embed-text", description="Ollama embedding model name")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Base URL of local Ollama server")
    LLM_TEMPERATURE: float = Field(default=0.1, description="Sampling temperature for deterministic explanations")
    LLM_TIMEOUT_SECONDS: int = Field(default=120, description="Timeout in seconds for LLM generation")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins if provided as comma-separated string or list."""
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                # Handle JSON string format if passed in env
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        """Calculate max upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
