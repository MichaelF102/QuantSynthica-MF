from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="QSMF_", extra="ignore")

    database_url: str = "postgresql+psycopg://qsmf:qsmf@localhost:5433/qsmf"
    redis_url: str = "redis://localhost:6380/0"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    environment: str = "development"
    # New backtests load the whole NAV universe (about 1 GB). Switch off on small hosts; stored results are still served.
    enable_backtests: bool = True
    admin_token: str | None = None  # enables /api/v1/admin/* for the scheduler; unset = endpoints return 404
    anthropic_api_key: str | None = None  # optional: enables the assistant's validated model interpretation
    # bronze/silver/gold and reference files live here (set QSMF_DATA_DIR in containers)
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"

    @model_validator(mode="after")
    def _normalise_database_url(self) -> "Settings":
        # Render (and Heroku-style hosts) hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver named.
        for prefix in ("postgres://", "postgresql://"):
            if self.database_url.startswith(prefix):
                self.database_url = "postgresql+psycopg://" + self.database_url[len(prefix):]
        return self

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.environment == "production":
            if "qsmf:qsmf@" in self.database_url:
                raise ValueError("QSMF_DATABASE_URL still uses the development password; set real credentials from a secret manager")
            if any("localhost" in o for o in self.cors_origins):
                raise ValueError("QSMF_CORS_ORIGINS must list the real frontend origin in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
