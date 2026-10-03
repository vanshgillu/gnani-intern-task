from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    supabase_url: str
    supabase_service_key: str
    supabase_bucket: str = "audio"

    gnani_api_key: str
    gnani_base_url: str = "https://api.vachana.ai"
    gnani_model: str = "gnani-prisma-v2.5"
    gnani_poll_interval_seconds: int = 10
    gnani_timeout_seconds: int = 2 * 60 * 60

    groq_api_key: str
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    cookie_name: str = "guest_user_id"
    cookie_secure: bool = False
    # supabase free tier limit
    max_upload_mb: int = 50

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
