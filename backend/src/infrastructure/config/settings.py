"""Application configuration settings."""

from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Application
    app_name: str = "Voice Sales Agent"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")
    
    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        alias="CORS_ORIGINS"
    )
    
    # Shopify
    shopify_store_url: str = Field(alias="SHOPIFY_STORE_URL")
    shopify_access_token: str = Field(alias="SHOPIFY_ACCESS_TOKEN")
    shopify_api_version: str = Field(default="2024-01", alias="SHOPIFY_API_VERSION")
    
    # OpenAI
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")
    
    # Deepgram
    deepgram_api_key: Optional[str] = Field(default=None, alias="DEEPGRAM_API_KEY")
    deepgram_model: str = Field(default="nova-2", alias="DEEPGRAM_MODEL")
    
    # Cartesia
    cartesia_api_key: Optional[str] = Field(default=None, alias="CARTESIA_API_KEY")
    cartesia_model: str = Field(default="sonic-3", alias="CARTESIA_MODEL")
    cartesia_voice_id: str = Field(default="f786b574-daa5-4673-aa0c-cbe3e8534c02", alias="CARTESIA_VOICE_ID")  # Default voice
    cartesia_language: str = Field(default="en", alias="CARTESIA_LANGUAGE")
    cartesia_speed: float = Field(default=1.0, alias="CARTESIA_SPEED")  # 1.0 = normal, 0.5 = slow, 2.0 = fast
    
    # LiveKit
    livekit_url: str = Field(alias="LIVEKIT_URL")
    livekit_api_key: str = Field(alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(alias="LIVEKIT_API_SECRET")
    livekit_room_prefix: str = Field(default="voice-agent", alias="LIVEKIT_ROOM_PREFIX")
    
    # Redis (optional)
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    cache_ttl: int = Field(default=300, alias="CACHE_TTL")  # 5 minutes
    
    # Database (optional)
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    
    # Session
    session_ttl: int = Field(default=3600, alias="SESSION_TTL")  # 1 hour
    max_sessions_per_user: int = Field(default=5, alias="MAX_SESSIONS_PER_USER")
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, alias="RATE_LIMIT_PERIOD")  # seconds
    
    # Voice processing
    vad_enabled: bool = Field(default=True, alias="VAD_ENABLED")
    vad_threshold: float = Field(default=0.5, alias="VAD_THRESHOLD")
    stt_language: str = Field(default="en-US", alias="STT_LANGUAGE")
    tts_voice: str = Field(default="alloy", alias="TTS_VOICE")
    
    # Agent behavior
    agent_max_retries: int = Field(default=3, alias="AGENT_MAX_RETRIES")
    agent_timeout: int = Field(default=30, alias="AGENT_TIMEOUT")  # seconds
    agent_context_window: int = Field(default=10, alias="AGENT_CONTEXT_WINDOW")  # messages
    
    # Feature flags
    enable_voice: bool = Field(default=True, alias="ENABLE_VOICE")
    enable_chat: bool = Field(default=True, alias="ENABLE_CHAT")
    enable_analytics: bool = Field(default=True, alias="ENABLE_ANALYTICS")
    enable_recommendations: bool = Field(default=False, alias="ENABLE_RECOMMENDATIONS")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env.lower() == "development"
    
    @property
    def shopify_base_url(self) -> str:
        """Get Shopify API base URL."""
        return f"https://{self.shopify_store_url}/admin/api/{self.shopify_api_version}"
    
    def get_redis_config(self) -> Optional[dict]:
        """Get Redis configuration."""
        if not self.redis_url:
            return None
        
        return {
            "url": self.redis_url,
            "decode_responses": True,
            "health_check_interval": 30
        }
    
    def get_livekit_config(self) -> dict:
        """Get LiveKit configuration."""
        return {
            "url": self.livekit_url,
            "api_key": self.livekit_api_key,
            "api_secret": self.livekit_api_secret,
            "room_prefix": self.livekit_room_prefix
        }
    
    def mask_sensitive(self) -> dict:
        """Get settings with masked sensitive values."""
        data = self.model_dump()
        sensitive_keys = [
            "shopify_access_token",
            "openai_api_key",
            "deepgram_api_key",
            "cartesia_api_key",
            "livekit_api_key",
            "livekit_api_secret",
            "database_url",
            "redis_url"
        ]
        
        for key in sensitive_keys:
            if key in data and data[key]:
                data[key] = "***" + data[key][-4:] if len(data[key]) > 4 else "****"
        
        return data


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance."""
    return settings