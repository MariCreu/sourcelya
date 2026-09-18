from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProductionConfigError(RuntimeError):
    """Raised at startup when running in production with a config that would
    otherwise fail silently — e.g. falling back to in-memory storage that
    loses every uploaded document on the next restart. Crashing the process
    is deliberate: a deploy that can't start is visible in Render's logs and
    health checks immediately, where a silent fallback would not surface
    until a customer noticed missing data or a lost email.
    """


def docs_urls_for_environment(environment: str) -> tuple[str | None, str | None, str | None]:
    """(docs_url, redoc_url, openapi_url) for `FastAPI(...)`.

    Interactive docs reveal the full schema — every field, every internal
    endpoint — to anyone who finds the URL. Fine for local/dev; not for a
    production API handling suppliers' compliance documents. Returns all
    three as None (FastAPI's own way of disabling them) outside dev/test.
    """
    if environment == "production":
        return None, None, None
    return "/docs", "/redoc", "/openapi.json"


def validate_production_config(settings: Settings) -> None:
    """Fails loud on production misconfigurations that would otherwise
    degrade silently, and warns (without crashing) on the ones that are
    expected to be temporarily unset while a feature is being rolled out —
    see docs/PRODUCTION-READINESS.md for which integrations are live.

    A no-op outside `environment == "production"` — local/dev/test setups
    are expected to run with fallbacks (in-memory storage, console email).
    """
    if settings.environment != "production":
        return

    errors: list[str] = []

    if not settings.supabase_url or not settings.supabase_service_role_key:
        errors.append(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not both set — "
            "storage would silently fall back to in-memory (documents lost "
            "on every restart, see app/integrations/storage/factory.py)."
        )

    if settings.frontend_base_url == "http://localhost:4200":
        errors.append(
            "FRONTEND_BASE_URL is still the local-dev default — CORS would "
            "reject every request from the real frontend, and supplier "
            "request links would point at localhost."
        )

    if settings.supabase_jwt_strategy == "hs256":
        errors.append(
            "SUPABASE_JWT_STRATEGY=hs256 in production — this is the "
            "shared-secret fallback meant for local/offline dev only; "
            "production must verify against Supabase's real JWKS."
        )

    if errors:
        for message in errors:
            logger.error("production_config_invalid", detail=message)
        raise ProductionConfigError(
            f"Refusing to start in production with {len(errors)} invalid "
            f"config value(s) — see the error log above for details."
        )

    if not settings.resend_api_key:
        logger.warning(
            "production_config_degraded",
            detail="RESEND_API_KEY is not set — emails are only logged, "
            "not actually sent to suppliers.",
        )

    if settings.document_extraction_provider == "stub":
        logger.warning(
            "production_config_degraded",
            detail="DOCUMENT_EXTRACTION_PROVIDER=stub — uploaded documents "
            "will never get extraction suggestions.",
        )

    if settings.malware_scan_provider == "stub":
        logger.warning(
            "production_config_degraded",
            detail="MALWARE_SCAN_PROVIDER=stub — uploaded files are never "
            "actually scanned for malware.",
        )

    if not settings.internal_jobs_secret:
        logger.warning(
            "production_config_degraded",
            detail="INTERNAL_JOBS_SECRET is not set — POST "
            "/internal/jobs/process-reminders will always reject requests, "
            "so reminder emails will never be sent.",
        )
