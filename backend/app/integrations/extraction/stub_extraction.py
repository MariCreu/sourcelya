from app.integrations.extraction.base import DocumentExtractionService, ExtractedFieldSuggestion


class StubDocumentExtractionService(DocumentExtractionService):
    """No real AI/OCR call is wired up yet (see product spec section 13/29:
    extraction is not the FASE 1-6 priority).

    Returns no suggestions, so uploaded documents stay attached to the
    request/product but their `extraction_status` is left for
    DocumentService to move to FAILED/PENDING rather than silently
    fabricating data. Swap this out behind DocumentExtractionService in
    FASE 7 for a real provider — nothing above this layer changes.
    """

    def extract(
        self, *, file_bytes: bytes, filename: str, content_type: str
    ) -> list[ExtractedFieldSuggestion]:
        return []
