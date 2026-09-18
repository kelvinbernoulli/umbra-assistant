"""
Central application configuration.

All secrets/config load from environment variables (see .env.template).
Nothing in this module should be hardcoded — if you find yourself typing
a real key here, stop and put it in .env instead.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Umbra Assistant"
    APP_PORT: int = 8080
    APP_ENV: str | None = None  # local | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./umbra.db"
    MAX_INGESTION_ATTEMPTS: int = 3
    RETRY_SCHEDULER_ENABLED: bool = False
    RETRY_INTERVAL_SECONDS: int = 300
    RETRY_BATCH_LIMIT: int = 100

    # --- Browser authentication ---
    FRONTEND_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://localhost:4173", "https://umbra-assistant-ui.vercel.app"]
    SESSION_COOKIE_SECURE: bool = True
    SECRET_KEY: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # --- Pinecone ---
    PINECONE_API_KEY: str | None = None
    PINECONE_INDEX_NAME: str = "umbra-assistant"
    PINECONE_ENVIRONMENT: str | None = None

    # --- Hugging Face ---
    HUGGINGFACE_API_TOKEN: str | None = None
    HUGGINGFACE_EMBEDDING_MODEL: str | None = None
    HUGGINGFACE_EMBEDDING_DIM: int = 1024
    HUGGINGFACE_SYNTHESIS_MODEL: str | None = None  # e.g. an HF Inference Endpoint URL or model id

    # --- Webhooks / Integrations ---
    WHATSAPP_VERIFY_TOKEN: str | None = None
    WHATSAPP_APP_SECRET: str | None = None
    SENDGRID_INBOUND_SECRET: str | None = None
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_CALLBACK_URL: str

    # --- Credential store (encrypted token storage, NOT Pinecone) ---
    CREDENTIAL_DB_URL: str | None = None  # e.g. sqlite:///./data/credentials.db
    CREDENTIAL_ENCRYPTION_KEY: str | None = None  # required in staging/production

    # --- Retention ---
    MESSAGE_TTL_DAYS: int = 90
    SUMMARY_TTL_DAYS: int = 730



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()