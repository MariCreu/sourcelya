from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration.

    Every value that could vary between environments or that shows up more
    than once in the codebase (reminder cadence, upload limits, token
    lifetime, ...) must be read from here. Nothing environment-specific
    should be hardcoded elsewhere.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "PackProof API"
    environment: str = "development"
    debug: bool = True
    frontend_base_url: str = "http://localhost:4200"
    api_v1_prefix: str = "/api"

    # Database
    database_url: str = "postgresql+psycopg://packproof:packproof@localhost:5432/packproof"

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = "dev-secret-change-me"
    supabase_storage_bucket: str = "packproof-documents"

    # Auth / tokens
    jwt_algorithm: str = "HS256"
    supplier_token_bytes: int = 32
    supplier_token_default_expiry_days: int = 30

    # Reminders (centralized, never hardcode elsewhere)
    reminder_schedule_days: List[int] = [3, 7, 14]

    # Uploads
    max_upload_size_mb: int = 20
    allowed_upload_extensions: List[str] = ["pdf", "xlsx", "csv", "docx", "png", "jpg", "jpeg"]

    # Email
    resend_api_key: str = ""
    email_from_address: str = "PackProof <notifications@packproof.dev>"

    # Extraction
    document_extraction_provider: str = "stub"


@lru_cache
def get_settings() -> Settings:
    return Settings()
