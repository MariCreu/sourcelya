from app.domain.enums import DocumentType
from app.integrations.extraction.base import DocumentExtractionResult, DocumentExtractionService


class StubDocumentExtractionService(DocumentExtractionService):
    """The default when `DOCUMENT_EXTRACTION_PROVIDER` isn't `anthropic`
    (e.g. no API key configured yet). Returns no suggestions and an
    unclassified document, so uploaded documents stay attached to the
    request/product without ever fabricating data — see
    `ClaudeDocumentExtractionService` for the real implementation.
    """

    def extract(
        self, *, file_bytes: bytes, filename: str, content_type: str
    ) -> DocumentExtractionResult:
        return DocumentExtractionResult(
            document_classification=DocumentType.OTHER.value,
            fields=[],
            model="stub",
            input_tokens=0,
            output_tokens=0,
            duration_ms=0,
            estimated_cost_usd=0.0,
        )
