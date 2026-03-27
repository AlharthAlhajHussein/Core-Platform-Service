from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    app_name: str = "Core Platform API"
    app_version: str = "1.0.0"
    
    # Database
    db_user: str | None
    db_password: str | None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str | None

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None

    # Security
    secret_key: str | None = "secret_key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Encryption
    fernet_key: bytes | None = None

    # Internal Services
    rag_service_url: str | None = None
    internal_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()