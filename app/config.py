"""Application settings loaded from environment variables (.env supported).

No secret has a hardcoded production value: every sensitive setting must be
provided through the environment. `.env.example` documents each variable.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SOUNDACCESS_", env_file=".env", extra="ignore"
    )

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "https://auth.soundaccess.local"
    jwt_audience: str = "https://api.soundaccess.local"
    access_token_minutes: int = 15

    # OAuth
    auth_code_seconds: int = 60
    client_registration_key: str

    # Persistence
    database_url: str = "sqlite:///./soundaccess.db"

    # CORS (comma-separated origins; wildcard is intentionally not supported)
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"

    # Development seeding only
    seed_user_password: str = ""
    seed_service_secret: str = ""
    # Task 3: secret for the legacy ROPC client ("legacy-client"). Kept
    # separate from seed_service_secret (client_credentials) so each grant's
    # demo client has its own independently rotatable credential.
    seed_legacy_client_secret: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
