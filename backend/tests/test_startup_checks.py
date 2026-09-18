import pytest

from app.core.config import Settings
from app.core.startup_checks import (
    ProductionConfigError,
    docs_urls_for_environment,
    validate_production_config,
)

_VALID_PRODUCTION_OVERRIDES = dict(
    environment="production",
    supabase_url="https://pqvaqsvcfapiuhgfwlon.supabase.co",
    supabase_service_role_key="real-key",
    frontend_base_url="https://app.sourcelya.com",
    supabase_jwt_strategy="jwks",
)


def _settings(**overrides) -> Settings:
    return Settings(**{**_VALID_PRODUCTION_OVERRIDES, **overrides})


def test_noop_outside_production():
    # Every field here would fail the production checks — proves the
    # function does nothing unless environment == "production".
    settings = Settings(
        environment="test",
        supabase_url="",
        supabase_service_role_key="",
        frontend_base_url="http://localhost:4200",
        supabase_jwt_strategy="hs256",
    )
    validate_production_config(settings)  # must not raise


def test_valid_production_config_passes():
    validate_production_config(_settings())  # must not raise


def test_raises_when_storage_would_fall_back_to_memory():
    settings = _settings(supabase_url="", supabase_service_role_key="")
    with pytest.raises(ProductionConfigError):
        validate_production_config(settings)


def test_raises_when_frontend_base_url_is_still_the_dev_default():
    settings = _settings(frontend_base_url="http://localhost:4200")
    with pytest.raises(ProductionConfigError):
        validate_production_config(settings)


def test_raises_when_jwt_strategy_is_the_dev_fallback():
    settings = _settings(supabase_jwt_strategy="hs256")
    with pytest.raises(ProductionConfigError):
        validate_production_config(settings)


def test_passes_with_only_degraded_warnings(caplog):
    # resend/extraction/internal-jobs being unset is expected mid-rollout —
    # it should warn, not crash. See docs/PRODUCTION-READINESS.md.
    settings = _settings(
        resend_api_key="",
        document_extraction_provider="stub",
        internal_jobs_secret="",
    )
    validate_production_config(settings)  # must not raise


def test_docs_disabled_in_production():
    assert docs_urls_for_environment("production") == (None, None, None)


@pytest.mark.parametrize("environment", ["development", "test", "staging"])
def test_docs_enabled_outside_production(environment):
    assert docs_urls_for_environment(environment) == ("/docs", "/redoc", "/openapi.json")
