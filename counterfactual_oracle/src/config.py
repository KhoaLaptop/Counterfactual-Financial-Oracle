"""
Centralized configuration management for Counterfactual Financial Oracle.
Uses pydantic-settings for environment-based configuration with validation.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # ==========================================
    # Application
    # ==========================================
    app_name: str = "Counterfactual Financial Oracle"
    app_version: str = "2.4.1"
    debug: bool = False
    environment: str = "development"  # development, staging, production
    
    # ==========================================
    # Security
    # ==========================================
    # API Keys (should be set via environment variables)
    landingai_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    
    # File Upload Security
    max_pdf_size_mb: int = 50
    allowed_extensions: list[str] = [".pdf", ".json"]
    upload_timeout_seconds: int = 900
    
    # Encryption
    encryption_key: Optional[str] = None  # For sensitive temp files
    
    # ==========================================
    # Simulation
    # ==========================================
    monte_carlo_iterations: int = 10_000
    default_wacc: float = 0.08
    terminal_growth_rate: float = 0.02
    forecast_years: int = 5
    random_seed: int = 42
    
    # ==========================================
    # Document Extraction
    # ==========================================
    landing_ai_timeout: int = 900
    landing_ai_base_url: str = "https://api.va.landing.ai/v1/ade"
    landing_ai_max_retries: int = 3
    landing_ai_retry_delay: float = 4.0
    
    # ==========================================
    # AI/LLM Configuration
    # ==========================================
    # DeepSeek
    deepseek_model: str = "DeepSeek-V3.2-Speciale"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_timeout: int = 60
    deepseek_max_retries: int = 3
    
    # OpenAI
    openai_model: str = "gpt-4-turbo"
    openai_timeout: int = 60
    openai_max_retries: int = 3
    
    # Gemini
    gemini_model: str = "gemini-3.0-pro"
    gemini_timeout: int = 60
    
    # ==========================================
    # Debate Configuration
    # ==========================================
    max_debate_rounds: int = 10
    convergence_threshold: int = 2
    debate_rate_limit_delay: float = 2.0  # seconds between calls
    debate_convergence_check_interval: int = 2
    
    # ==========================================
    # Caching
    # ==========================================
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000
    redis_url: Optional[str] = None  # If None, use in-memory cache
    
    # ==========================================
    # Observability
    # ==========================================
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    enable_telemetry: bool = True
    prometheus_port: int = 9090
    jaeger_endpoint: Optional[str] = None
    
    # ==========================================
    # Database
    # ==========================================
    database_url: str = "sqlite:///counterfactual.db"
    database_echo: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Using lru_cache ensures we don't reload settings on every call.
    """
    return Settings()


def validate_settings() -> list[str]:
    """
    Validate that required settings are configured.
    Returns list of missing required settings.
    """
    settings = get_settings()
    missing = []
    
    required_in_prod = [
        "landingai_api_key",
        "openai_api_key",
        "deepseek_api_key",
    ]
    
    if settings.environment == "production":
        for key in required_in_prod:
            if not getattr(settings, key):
                missing.append(key)
    
    return missing


# Global settings instance
settings = get_settings()
