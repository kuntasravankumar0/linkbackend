"""
Application settings loaded from .env file.
Uses pydantic-settings for type-safe config with validation.
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings

# Always resolve .env relative to the backend root, regardless of cwd
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_ENV_FILE = os.path.join(_BACKEND_ROOT, ".env")
_ENV_BACKEND_FILE = os.path.join(_BACKEND_ROOT, ".envbackend")


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────────────────────
    DB_HOST:     str           = "localhost"
    DB_PORT:     int           = 3306
    DB_USER:     str           = "root"
    DB_PASSWORD: str           = "yourpassword"
    DB_NAME:     str           = "defaultdb"
    DB_SSL_CA:   Optional[str] = None   # e.g. "ssl/ca.pem" for Aiven
    DB_FALLBACK_SQLITE: bool   = True    # Set False in production via env var
    SQLITE_DB_FILE: str        = "local_dev.db"

    # ── App ────────────────────────────────────────────────────────────────────
    APP_HOST: str  = "0.0.0.0"
    APP_PORT: int  = 8081
    DEBUG:    bool = True

    # ── CORS — comma-separated list of allowed origins ─────────────────────────
    CORS_ORIGINS: str = "https://linkfrontend.onrender.com,http://localhost:3000"
    ADMIN_KEY_HASH: str = "31296e7fe96a8441e7ec335812a3a5777c046269d7c132800858b2dcfec56e01"

    # ── Computed properties ────────────────────────────────────────────────────

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL for MySQL via PyMySQL."""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    @property
    def sqlite_url(self) -> str:
        """Local fallback DB URL for development when cloud MySQL is unreachable."""
        return f"sqlite:///{os.path.join(_BACKEND_ROOT, self.SQLITE_DB_FILE)}"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {
        "env_file": (_ENV_FILE, _ENV_BACKEND_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton — imported everywhere as `from app.config.settings import settings`
settings = Settings()
