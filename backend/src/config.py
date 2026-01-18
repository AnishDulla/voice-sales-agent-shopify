"""Application configuration and settings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from pathlib import Path
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # Application
    app_name: str = "Voice Commerce Backend"
    app_version: str = "2.0.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False)
    
    # Shopify
    shopify_store_url: str = Field(..., alias="SHOPIFY_STORE_URL")
    shopify_access_token: str = Field(..., alias="SHOPIFY_ACCESS_TOKEN")
    shopify_api_version: str = Field(default="2024-01", alias="SHOPIFY_API_VERSION")
    
    # OpenAI (optional, for potential direct usage)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    
    # Retell AI
    retell_api_key: Optional[str] = Field(default=None, alias="RETELL_API_KEY")
    
    # CORS
    cors_origins: List[str] = Field(default=["*"], alias="CORS_ORIGINS")
    
    # Redis (optional)
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    
    # Session
    session_ttl: int = Field(default=3600, alias="SESSION_TTL")
    
    class Config:
        """Pydantic configuration."""
        env_file = Path(__file__).parent.parent / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.debug = settings.is_development
    return settings