from typing import Protocol


class StorageService(Protocol):
    """Port for document storage. DocumentService (FASE 4) is the only
    caller — it decides the path convention (`companies/{companyId}/...`)
    so tenant isolation lives at the storage layer too, not just in SQL.
    """

    def upload(self, *, path: str, content: bytes, content_type: str) -> str:
        """Stores the file and returns the storage path (not a public URL)."""
        ...

    def download(self, *, path: str) -> bytes:
        """Returns the raw file content. `DocumentService` streams this back
        through `GET /api/documents/{id}/download` rather than redirecting
        the browser to a signed URL — one code path works the same way in
        tests, local dev (no real Supabase project needed) and production.
        """
        ...

    def create_signed_url(self, *, path: str, expires_in_seconds: int = 3600) -> str:
        """Returns a short-lived URL a browser can use to download/view the file."""
        ...

    def delete(self, *, path: str) -> None: ...
