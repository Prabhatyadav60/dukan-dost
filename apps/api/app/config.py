from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    mongo_uri: str = "memory"  # "memory" = in-process mongomock, else a real MongoDB URI
    mongo_db: str = "dukan_dost"
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_ttl_minutes: int = 720
    demo_phone: str = "+919999900001"
    demo_otp: str = "123456"
    demo_today: str = "2026-10-31"
    demo_customer_phones: str = ""

    ai_provider: str = "fake"  # live | fake
    llm_backend: str = "anthropic"  # anthropic | bedrock
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    aws_region: str = "ap-south-1"
    bedrock_model_id: str = "anthropic.claude-opus-5-5"
    sarvam_api_key: str = ""

    public_web_url: str = "http://localhost:5173"
    web_origin: str = "http://localhost:5173"
    payment_webhook_secret: str = "dev-only-webhook-secret-0123456789abcdef"
    pay_link_ttl_hours: int = 72
    upload_dir: str = "./data/uploads"
    ai_rate_limit_per_min: int = 20
    feature_shelf_scan: bool = True
    forecast_margin: float = 0.10
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
