from functools import lru_cache

from app.core.config import get_settings
from app.integrations.extraction.base import DocumentExtractionService
from app.integrations.extraction.stub_extraction import StubDocumentExtractionService


@lru_cache
def get_extraction_service() -> DocumentExtractionService:
    settings = get_settings()
    if settings.document_extraction_provider == "stub":
        return StubDocumentExtractionService()
    raise ValueError(
        f"Unknown DOCUMENT_EXTRACTION_PROVIDER '{settings.document_extraction_provider}'"
    )
