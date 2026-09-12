from functools import lru_cache
from typing import List, Literal

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
    supabase_storage_bucket: str = "packproof-documents"

    # --- Auth / JWT verification ---
    # "jwks" (default, production): Supabase's current recommended approach —
    # asymmetric signing keys verified against the project's JWKS endpoint.
    # "hs256": a shared secret, only for local/offline dev or tests that can't
    # reach a real Supabase project. Defaulting to "jwks" means a forgotten
    # env var fails safe (towards the stronger verification), not silently
    # weak. See app/core/security.py.
    supabase_jwt_strategy: Literal["jwks", "hs256"] = "jwks"
    supabase_jwks_url: str = ""  # override; defaults to f"{supabase_url}/auth/v1/.well-known/jwks.json"
    supabase_issuer: str = ""  # override; defaults to f"{supabase_url}/auth/v1"
    supabase_jwt_allowed_algorithms: List[str] = ["ES256", "RS256"]
    supabase_jwt_secret: str = "dev-secret-change-me"  # only used when strategy == "hs256"

    supplier_token_bytes: int = 32
    supplier_token_default_expiry_days: int = 30

    # Internal jobs (e.g. POST /internal/jobs/process-reminders), called by
    # Supabase Cron / pg_cron rather than a logged-in user. Generate with
    # `openssl rand -hex 32`.
    internal_jobs_secret: str = ""

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

    @property
    def resolved_supabase_jwks_url(self) -> str:
        return self.supabase_jwks_url or f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def resolved_supabase_issuer(self) -> str:
        return self.supabase_issuer or f"{self.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
