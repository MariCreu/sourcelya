from dataclasses import dataclass
from typing import Protocol


class ExtractionError(Exception):
    """Raised by a DocumentExtractionService implementation when a document
    could not be processed (provider error, unreadable file, ...).
    ExtractionService catches this, marks the SupplierDocument FAILED with
    the message, and leaves the original file untouched — see that
    service's docstring for the retry story.
    """


@dataclass(frozen=True)
class ExtractedFieldSuggestion:
    """One field suggestion out of a document, with evidence.

    This is the normalized shape every DocumentExtractionService
    implementation must return, regardless of which LLM/OCR provider sits
    behind it. `ExtractionService` turns each of these into an
    `ExtractedField` row — it never overwrites confirmed
    `PackagingComponent` data itself; only an explicit human ACCEPT does
    (see `ExtractedFieldService`).

    Only ever produced for a field the provider reported as actually
    FOUND (never for NOT_FOUND/UNKNOWN — see `DocumentExtractionService.extract`).
    `confidence` is one of `app.domain.enums.ConfidenceLevel`'s values,
    already resolved by the provider adapter using its own verification
    rule — never a raw, unfounded number from the model. See
    `claude_extraction.py`'s module docstring for exactly how it's derived.
    """

    field_name: str
    value: str
    confidence: str
    source_page: int | None = None
    source_quote: str | None = None
    quote_verified: bool = False


@dataclass(frozen=True)
class DocumentExtractionResult:
    """Everything one `extract()` call produces: the proposed fields, the
    document's own classification, and enough usage/cost bookkeeping to
    answer "what does processing 1,000 documents cost" later — see the
    FASE 5 spec's "coste" section. `model`/`input_tokens`/`output_tokens`/
    `estimated_cost_usd` are `""`/`0`/`0`/`0.0` for a provider that isn't a
    real paid call (`StubDocumentExtractionService`).
    """

    document_classification: str
    fields: list[ExtractedFieldSuggestion]
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    estimated_cost_usd: float


class DocumentExtractionService(Protocol):
    """Domain port for document understanding.

    The domain (services/repositories) only ever talks to this interface,
    never to a specific AI/OCR vendor's SDK. Swapping providers later means
    writing a new adapter here, nothing else changes. Must never raise
    anything other than `ExtractionError` — any provider-specific
    exception should be caught and re-raised as one, so `ExtractionService`
    has one failure shape to handle regardless of provider.
    """

    def extract(
        self, *, file_bytes: bytes, filename: str, content_type: str
    ) -> DocumentExtractionResult: ...
