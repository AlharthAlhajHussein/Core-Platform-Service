from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    app_name: str = "Core Platform API"
    app_version: str = "1.0.0"
    
    # Database
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    db_name: str

    # Redis
    redis_host: str
    redis_port: int
    redis_password: str | None = None

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Encryption
    fernet_key: bytes

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()