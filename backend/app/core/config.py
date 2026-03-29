from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Supabase Storage
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Email
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@xpensa.app"
    FROM_NAME: str = "Xpensa"

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Currency
    EXCHANGE_RATE_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()