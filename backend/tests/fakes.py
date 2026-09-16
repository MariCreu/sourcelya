from app.integrations.email.base import EmailMessage, EmailSender
from app.integrations.extraction.base import (
    DocumentExtractionResult,
    DocumentExtractionService,
    ExtractionError,
)
from app.integrations.malware.base import MalwareDetectedError, MalwareScanUnavailableError


class RecordingEmailSender(EmailSender):
    """Test double: never talks to a real provider, just remembers every
    message so a test can assert on subject/body/recipient — e.g. pulling
    the request URL out of a sent email the way a real supplier would.
    """

    def __init__(self):
        self.sent_messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent_messages.append(message)


class FakeDocumentExtractionService(DocumentExtractionService):
    """Deterministic test double for `DocumentExtractionService` — the fast
    suite must never depend on a real, paid Claude call (see the FASE 5
    spec's "usar fixtures deterministas ... no hacer que la suite normal
    dependa de llamadas pagadas a un LLM"). Configure `result` (or
    `error`) up front; `extract()` just returns/raises it and records the
    call args for assertions.
    """

    def __init__(
        self, result: DocumentExtractionResult | None = None, error: Exception | None = None
    ):
        self.result = result
        self.error = error
        self.calls: list[dict] = []

    def extract(
        self, *, file_bytes: bytes, filename: str, content_type: str
    ) -> DocumentExtractionResult:
        self.calls.append(
            {"file_bytes": file_bytes, "filename": filename, "content_type": content_type}
        )
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return DocumentExtractionResult(
            document_classification="other",
            fields=[],
            model="fake",
            input_tokens=0,
            output_tokens=0,
            duration_ms=0,
            estimated_cost_usd=0.0,
        )


class FakeMalwareScanner:
    """Test double for `MalwareScanner` — lets a test force "infected" or
    "scanner unavailable" without a real ClamAV daemon. Clean by default,
    matching `StubMalwareScanner`'s real-world default.
    """

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[bytes] = []

    def scan(self, *, content: bytes) -> None:
        self.calls.append(content)
        if self.error is not None:
            raise self.error


def infected_file_error() -> MalwareDetectedError:
    return MalwareDetectedError("File flagged by ClamAV: Eicar-Test-Signature")


def scanner_unavailable_error() -> MalwareScanUnavailableError:
    return MalwareScanUnavailableError("ClamAV scan failed: connection refused")
