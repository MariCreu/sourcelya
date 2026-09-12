from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExtractedFieldSuggestion:
    """One field suggestion out of a document, with provenance.

    This is the normalized shape every DocumentExtractionService
    implementation must return, regardless of which LLM/OCR provider sits
    behind it. DocumentService turns each of these into an ExtractedField
    row — it never overwrites confirmed data itself (see ExtractedField
    model docstring and FASE 7 conflict-handling rules).
    """

    field_name: str
    value: str
    confidence: float | None
    source_page: int | None = None
    source_text: str | None = None


class DocumentExtractionService(Protocol):
    """Domain port for document understanding.

    The domain (services/repositories) only ever talks to this interface,
    never to a specific AI/OCR vendor's SDK — see product spec section 4.
    Swapping providers later means writing a new adapter here, nothing else
    changes.
    """

    def extract(
        self, *, file_bytes: bytes, filename: str, content_type: str
    ) -> list[ExtractedFieldSuggestion]: ...
