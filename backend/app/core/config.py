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
    BABELDOC_OFFLINE_EXPORT_DIR: str = os.path.join(OUTPUT_DIR, "offline-assets")

    # Translation queue
    MAX_CONCURRENT_TRANSLATIONS: int = 2
    MAX_QUEUE_SIZE: int = 100

    # Translation settings
    DEFAULT_QPS: int = 4
    BABELDOC_OFFLINE_MODE: bool = False
    BABELDOC_OFFLINE_ASSETS_PACKAGE: str | None = None
    BABELDOC_PRECHECK_ASSETS_ON_STARTUP: bool = False
    BABELDOC_OFFLINE_ASSET_PROFILE: str = "full"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
