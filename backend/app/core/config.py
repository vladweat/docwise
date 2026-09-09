from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "change_this_secret_key_in_prod"
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql://docwise:change_this_in_prod@localhost:5432/docwise_db",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    embedding_model_path: str = Field(default="", alias="EMBEDDING_MODEL_PATH")
    s3_endpoint: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT")
    s3_access_key: str = Field(default="docwise", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="change_this_in_prod", alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="documents", alias="S3_BUCKET")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default=DEFAULT_SECRET_KEY, alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    celery_broker_url: str = Field(default="redis://redis:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://redis:6379/0", alias="CELERY_RESULT_BACKEND")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="", alias="OPENAI_MODEL")
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    rate_limit_upload_per_minute: int = Field(default=10, alias="RATE_LIMIT_UPLOAD_PER_MINUTE")
    upload_max_bytes: int = Field(default=50 * 1024 * 1024, alias="UPLOAD_MAX_BYTES")
    rate_limit_chat_per_minute: int = Field(default=30, alias="RATE_LIMIT_CHAT_PER_MINUTE")
    rerank_threshold: float = Field(default=0.25, alias="RERANK_THRESHOLD")
    rate_limit_auth_per_minute: int = Field(default=20, alias="RATE_LIMIT_AUTH_PER_MINUTE")
    refresh_token_expire_minutes: int = Field(default=10080, alias="REFRESH_TOKEN_EXPIRE_MINUTES")
    cookie_samesite: str = Field(default="none", alias="COOKIE_SAMESITE")
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")
    cors_origins: str = Field(default=DEFAULT_CORS_ORIGINS, alias="CORS_ORIGINS")

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
