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
    enable_search_inspect: bool | None = Field(default=None, alias="ENABLE_SEARCH_INSPECT")
    rate_limit_auth_per_minute: int = Field(default=20, alias="RATE_LIMIT_AUTH_PER_MINUTE")
    refresh_token_expire_minutes: int = Field(default=10080, alias="REFRESH_TOKEN_EXPIRE_MINUTES")
    cookie_samesite: str = Field(default="none", alias="COOKIE_SAMESITE")
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")
    cors_origins: str = Field(default=DEFAULT_CORS_ORIGINS, alias="CORS_ORIGINS")
    plan_period_days: int = Field(default=30, alias="PLAN_PERIOD_DAYS")
    plan_starter_seats: int = Field(default=3, alias="PLAN_STARTER_SEATS")
    plan_starter_pages: int = Field(default=200, alias="PLAN_STARTER_PAGES")
    plan_starter_tokens: int = Field(default=100_000, alias="PLAN_STARTER_TOKENS")
    plan_team_seats: int = Field(default=15, alias="PLAN_TEAM_SEATS")
    plan_team_pages: int = Field(default=2_000, alias="PLAN_TEAM_PAGES")
    plan_team_tokens: int = Field(default=1_000_000, alias="PLAN_TEAM_TOKENS")
    plan_enterprise_seats: int = Field(default=100, alias="PLAN_ENTERPRISE_SEATS")
    plan_enterprise_pages: int = Field(default=20_000, alias="PLAN_ENTERPRISE_PAGES")
    plan_enterprise_tokens: int = Field(default=10_000_000, alias="PLAN_ENTERPRISE_TOKENS")
    billing_provider: str = Field(default="dev", alias="BILLING_PROVIDER")
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_starter: str = Field(default="", alias="STRIPE_PRICE_STARTER")
    stripe_price_team: str = Field(default="", alias="STRIPE_PRICE_TEAM")
    stripe_price_enterprise: str = Field(default="", alias="STRIPE_PRICE_ENTERPRISE")
    frontend_url: str = Field(default="", alias="FRONTEND_URL")
    sso_provider: str = Field(default="dev", alias="SSO_PROVIDER")
    sso_fresh_ttl_seconds: int = Field(default=900, alias="SSO_FRESH_TTL_SECONDS")

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def billing_provider_name(self) -> str:
        raw = (self.billing_provider or "dev").strip().lower()
        return raw or "dev"

    @property
    def stripe_configured(self) -> bool:
        return bool(self.stripe_secret_key.strip() and self.stripe_webhook_secret.strip())

    def stripe_price_id(self, plan: str) -> str:
        key = (plan or "").strip().lower()
        mapping = {
            "starter": self.stripe_price_starter,
            "team": self.stripe_price_team,
            "enterprise": self.stripe_price_enterprise,
        }
        return mapping.get(key, "").strip()

    @property
    def sso_provider_name(self) -> str:
        raw = (self.sso_provider or "dev").strip().lower()
        return raw or "dev"

    def public_frontend_url(self) -> str:
        explicit = self.frontend_url.strip().rstrip("/")
        if explicit:
            return explicit
        origins = self.cors_origin_list()
        return origins[0].rstrip("/") if origins else "http://localhost:3001"

    @property
    def search_inspect_enabled(self) -> bool:
        """Admin inspect endpoint. Off by default when ENVIRONMENT=production."""
        if self.enable_search_inspect is not None:
            return self.enable_search_inspect
        return self.environment.strip().lower() != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
