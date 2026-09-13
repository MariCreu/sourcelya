from functools import lru_cache

from app.core.config import get_settings
from app.integrations.extraction.base import DocumentExtractionService
from app.integrations.extraction.stub_extraction import StubDocumentExtractionService


@lru_cache
def get_extraction_service() -> DocumentExtractionService:
    settings = get_settings()
    if settings.document_extraction_provider == "stub":
        return StubDocumentExtractionService()
    if settings.document_extraction_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set when DOCUMENT_EXTRACTION_PROVIDER=anthropic"
            )
        from app.integrations.extraction.claude_extraction import ClaudeDocumentExtractionService

        return ClaudeDocumentExtractionService(
            api_key=settings.anthropic_api_key, model=settings.anthropic_extraction_model
        )
    raise ValueError(
        f"Unknown DOCUMENT_EXTRACTION_PROVIDER '{settings.document_extraction_provider}'"
    )
