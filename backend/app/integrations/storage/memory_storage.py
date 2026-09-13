from app.integrations.storage.base import StorageService


class InMemoryStorageService(StorageService):
    """Used when no Supabase project is configured (local dev, tests) — the
    same role `ConsoleEmailSender` plays for email. A plain process-lifetime
    dict: fine for a single-process dev server or a pytest run, but content
    does not survive a restart and isn't shared across workers. Swapping in
    `SupabaseStorageService` for production is a config change (set
    `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`), not a code change — see
    `factory.get_storage_service`.
    """

    def __init__(self):
        self._files: dict[str, bytes] = {}

    def upload(self, *, path: str, content: bytes, content_type: str) -> str:
        self._files[path] = content
        return path

    def download(self, *, path: str) -> bytes:
        return self._files[path]

    def create_signed_url(self, *, path: str, expires_in_seconds: int = 3600) -> str:
        return f"memory://{path}"

    def delete(self, *, path: str) -> None:
        self._files.pop(path, None)
