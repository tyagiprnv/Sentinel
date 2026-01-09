"""
Centralized configuration management for PII redaction system.

Uses pydantic-settings for type-safe configuration with environment variable support.
"""
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Redis Configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_ttl: int = 86400  # 24 hours in seconds
    redis_password: Optional[str] = None

    # Ollama LLM Configuration
    ollama_url: str = "http://ollama:11434/api/generate"
    ollama_model: str = "phi3"
    ollama_timeout: float = 30.0

    # Presidio Configuration
    presidio_score_threshold: float = 0.0  # Minimum confidence score (0.0 = detect all)
    presidio_language: str = "en"

    # LLM Prompt Configuration
    prompt_version: str = "v3_few_shot"  # Options: v1_basic, v2_cot, v3_few_shot
    use_chain_of_thought: bool = True
    few_shot_examples_count: int = 3

    # API Configuration
    api_title: str = "Sentinel - AI-Powered PII Protection"
    api_version: str = "1.0.0"
    api_debug: bool = False

    # Monitoring
    enable_metrics: bool = True
    enable_tracing: bool = False

    # Policy Engine
    enable_policy_engine: bool = True
    default_policy_context: str = "general"
    allow_policy_override: bool = True

    # Healthcare Policy Configuration
    healthcare_entities: List[str] = [
        "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN",
        "DATE_TIME", "LOCATION", "IP_ADDRESS"
    ]
    healthcare_allow_restore: bool = False
    healthcare_min_confidence: float = 0.5

    # Finance Policy Configuration
    finance_entities: List[str] = [
        "PERSON", "US_SSN", "CREDIT_CARD", "IBAN_CODE",
        "PHONE_NUMBER", "EMAIL_ADDRESS", "US_BANK_NUMBER", "US_DRIVER_LICENSE"
    ]
    finance_allow_restore: bool = False
    finance_min_confidence: float = 0.6

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings instance
    """
    return settings


def reload_settings():
    """Reload settings from environment (useful for testing)."""
    global settings
    settings = Settings()


if __name__ == "__main__":
    # Print current settings
    settings = get_settings()
    print("=== Current Configuration ===")
    print(f"Redis: {settings.redis_host}:{settings.redis_port}")
    print(f"Ollama: {settings.ollama_url} (model: {settings.ollama_model})")
    print(f"Prompt version: {settings.prompt_version}")
    print(f"Chain-of-thought: {settings.use_chain_of_thought}")
    print(f"Few-shot examples: {settings.few_shot_examples_count}")
