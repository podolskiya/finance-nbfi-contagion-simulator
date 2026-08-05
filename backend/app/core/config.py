"""
Application configuration.

Values here are read from environment variables (see .env.example).
Nothing sensitive is hardcoded — FFIEC and SEC EDGAR data are both public
and require no API keys, but we still centralize settings so Phase 1's
data pipeline and Phase 6's API share one source of truth.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NBFI Contagion Simulator API"
    environment: str = "development"

    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    extra_allowed_origins: str = ""

    @property
    def all_allowed_origins(self) -> list[str]:
        extra = [o.strip() for o in self.extra_allowed_origins.split(",") if o.strip()]
        return self.allowed_origins + extra

    sec_edgar_user_agent: str = "NBFI Contagion Simulator research@example.com"

    data_dir: str = "app/data_pipeline/processed"


@lru_cache
def get_settings() -> Settings:
    return Settings()