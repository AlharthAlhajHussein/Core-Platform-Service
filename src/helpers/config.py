import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dynamically resolve the absolute path to the src/.env file
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

class Settings(BaseSettings):
    
    app_name: str = "Core Platform API"
    app_version: str = "1.0.0"
    
    # Database
    db_user: str | None = None
    db_password: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str | None = None

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None

    # Security
    secret_key: str | None = None
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Encryption
    # Run this command to generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: bytes | None = None

    # RAG URL
    rag_service_url: str | None = None
    
    # secret key for auth between other services and core interanl endpoints
    core_internal_secret: str | None = None
    
    # For Telegram Webhook Registration (used by Channel Gateway)
    gateway_service_url: str | None = None
    telegram_webhook_secret: str | None = None

    model_config = SettingsConfigDict(env_file=env_path)


settings = Settings()