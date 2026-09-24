import re
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    # JSearch via RapidAPI. Optional: without it the JSearch source is
    # disabled and discovery runs on Adzuna + Greenhouse (see jobs/jsearch.py).
    rapidapi_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    demo_mode: bool = False
    # Keep development as the default so local/demo workflows need no extra
    # configuration. Deployments should explicitly set ENVIRONMENT=production
    # to enable production exposure checks at startup.
    environment: Literal["development", "production"] = "development"

    # JSON is the zero-config default for local development, tests, and demos.
    # Production deployments can opt into MongoDB Atlas explicitly.
    storage_backend: Literal["mongodb", "json"] = "json"
    mongodb_uri: str = ""
    mongodb_database: str = "careerstack"

    # No default: the app must not start on a guessable secret. Generate
    # one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("JWT_SECRET must not be blank")
        return value

    @field_validator("mongodb_database")
    @classmethod
    def mongodb_database_must_be_safe(cls, value: str) -> str:
        if not value.strip() or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("MONGODB_DATABASE must contain only letters, numbers, _ or -")
        return value

    @model_validator(mode="after")
    def mongodb_settings_must_be_complete(self) -> "Settings":
        if self.storage_backend == "mongodb" and not self.mongodb_uri.strip():
            raise ValueError(
                "MONGODB_URI is required when STORAGE_BACKEND=mongodb. "
                "Use the Atlas mongodb+srv:// connection string."
            )
        if self.mongodb_uri.strip() and not self.mongodb_uri.startswith(
            ("mongodb://", "mongodb+srv://")
        ):
            raise ValueError("MONGODB_URI must start with mongodb:// or mongodb+srv://")
        return self


settings = Settings()
