"""
Central configuration. All tunables come from environment variables / .env,
so nothing environment-specific is hard-coded in the app logic.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-5-nano-2025-08-07"

    # --- API auth (protects the API from being called by randoms) ---
    # If left empty, auth is disabled (fine for local dev, NOT for prod).
    API_KEY: str = ""

    # --- Conversation memory ---
    DB_PATH: str = "luniq_memory.db"
    MAX_TURNS: int = 5  # last N (user+assistant) turn-pairs kept per user

    # --- Rate limiting (simple per-user token bucket, single-instance) ---
    RATE_LIMIT_PER_MINUTE: int = 10

    # --- CORS ---
    ALLOWED_ORIGINS: str = "*"  # comma separated in prod, e.g. "https://app.luniq.com"

    # --- Misc ---
    ENVIRONMENT: str = "development"  # "development" | "production"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
