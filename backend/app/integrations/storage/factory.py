from functools import lru_cache

from app.core.config import get_settings
from app.integrations.storage.base import StorageService
from app.integrations.storage.memory_storage import InMemoryStorageService
from app.integrations.storage.supabase_storage import SupabaseStorageService


@lru_cache
def get_storage_service() -> StorageService:
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseStorageService(
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_storage_bucket,
        )
    return InMemoryStorageService()
