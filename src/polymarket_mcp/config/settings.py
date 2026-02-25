"""Application settings loaded from environment variables via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Polymarket API
    polymarket_data_api_base: str = "https://data-api.polymarket.com"
    polymarket_gamma_api_base: str = "https://gamma-api.polymarket.com"

    # HTTP client
    request_timeout: int = Field(default=30, ge=5, le=120)
    max_concurrency: int = Field(default=5, ge=1, le=20)

    # Logging
    log_level: str = "INFO"

    # MCP transport
    mcp_transport: str = Field(default="http", pattern="^(http|stdio)$")
    mcp_host: str = "0.0.0.0"
    mcp_port: int = Field(default=8000, ge=1024, le=65535)

    # Bot detection
    bot_detection_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # Cache
    cache_ttl: int = Field(default=300, ge=0)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
