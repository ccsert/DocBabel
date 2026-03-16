import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "BabelDOC Web"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://babeldoc:babeldoc@localhost:5432/babeldoc"

    # File storage
    UPLOAD_DIR: str = os.path.join(os.path.dirname(__file__), "..", "uploads")
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "outputs")

    # Translation queue
    MAX_CONCURRENT_TRANSLATIONS: int = 2
    MAX_QUEUE_SIZE: int = 100

    # Default translation settings
    DEFAULT_QPS: int = 4
    DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
