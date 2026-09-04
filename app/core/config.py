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
    APP_ENV: str | None = None  # local | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./umbra.db"
    MAX_INGESTION_ATTEMPTS: int = 3

    # --- Auth (placeholder — swap for real auth provider before prod) ---
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
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # --- Credential store (encrypted token storage, NOT Pinecone) ---
    CREDENTIAL_DB_URL: str | None = None  # e.g. sqlite:///./data/credentials.db
    CREDENTIAL_ENCRYPTION_KEY: str | None = None  # required in staging/production

    # --- Retention ---
    MESSAGE_TTL_DAYS: int = 90
    SUMMARY_TTL_DAYS: int = 730

    @property
    def use_mock_vectorstore(self) -> bool:
        """No Pinecone key configured -> fall back to an in-memory mock store."""
        return not self.PINECONE_API_KEY

    @property
    def use_mock_embeddings(self) -> bool:
        """No Hugging Face token configured -> fall back to a deterministic local mock embedder."""
        return not self.HUGGINGFACE_API_TOKEN


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()