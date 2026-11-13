from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://hf:hf@localhost:55432/hf_test"
    session_secret: str = "dev-only-change-me"
    family_password_hash: str = ""
    cookie_secure: bool = False
    worker_token: str = "dev-worker-token"
    server_url: str = "http://localhost:8000"
    photos_dir: str = "./data/photos"
    serve_photos: bool = False

    openai_api_key: str = ""
    openai_model_small: str = "gpt-5-mini"
    openai_model_large: str = "gpt-5"
    # USD per 1M tokens; update to current OpenAI pricing in .env
    openai_price_in_small: float = 0.25
    openai_price_out_small: float = 2.0
    openai_price_in_large: float = 1.25
    openai_price_out_large: float = 10.0
    openai_monthly_cap_usd: float = 20.0

    google_api_key: str = ""
    google_monthly_cap_usd: float = 50.0

    scrape_interval_hours: float = 4.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
