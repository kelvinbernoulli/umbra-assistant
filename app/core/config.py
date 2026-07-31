from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    HUGGINGFACEHUB_API_TOKEN: str
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str
    
    # App Settings
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Load from .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Global settings instance
settings = Settings()
