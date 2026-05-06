from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Literal["production", "development"] = "development"
    POSTGRES_CONNECTION_STRING: str
    ENABLE_DEV_PAGES: bool = False


settings = Settings()  # type: ignore[call-arg]
