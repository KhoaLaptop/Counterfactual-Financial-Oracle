"""Application configuration from environment variables"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Keys (optional - will fail at runtime if missing when needed)
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    landingai_api_key: str = ""
    
    # Database
    database_url: str = "sqlite:///./counterfactual.db"
    
    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    
    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Optional: Redis for background jobs
    redis_url: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()


