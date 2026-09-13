import httpx

from app.integrations.storage.base import StorageService


class SupabaseStorageService(StorageService):
    def __init__(self, supabase_url: str, service_role_key: str, bucket: str):
        self._base_url = f"{supabase_url}/storage/v1"
        self._bucket = bucket
        self._headers = {
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
        }

    def upload(self, *, path: str, content: bytes, content_type: str) -> str:
        response = httpx.post(
            f"{self._base_url}/object/{self._bucket}/{path}",
            content=content,
            headers={**self._headers, "Content-Type": content_type},
            timeout=30.0,
        )
        response.raise_for_status()
        return path

    def download(self, *, path: str) -> bytes:
        response = httpx.get(
            f"{self._base_url}/object/{self._bucket}/{path}",
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.content

    def create_signed_url(self, *, path: str, expires_in_seconds: int = 3600) -> str:
        response = httpx.post(
            f"{self._base_url}/object/sign/{self._bucket}/{path}",
            json={"expiresIn": expires_in_seconds},
            headers=self._headers,
            timeout=15.0,
        )
        response.raise_for_status()
        signed_path = response.json()["signedURL"]
        return f"{self._base_url}{signed_path}"

    def delete(self, *, path: str) -> None:
        response = httpx.request(
            "DELETE",
            f"{self._base_url}/object/{self._bucket}",
            json={"prefixes": [path]},
            headers=self._headers,
            timeout=15.0,
        )
        response.raise_for_status()
