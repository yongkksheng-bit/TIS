from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://postgres:Syk0215@db:5432/canteen_system"
    REDIS_URL: str = "redis://localhost:6379/0"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    DEEPSEEK_API_KEY: Optional[str] = None
    JWT_SECRET: str = "dev-secret-key-change-in-production"
    DEV_MODE: bool = True


settings = Settings()
