import uuid

from sqlalchemy.orm import Session

from app.core.security import SupabaseIdentity
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def get_or_create_from_identity(self, identity: SupabaseIdentity) -> User:
        """Mirrors the Supabase auth user into our own `users` table.

        Supabase owns signup/login; we only need a local row to attach a
        company and app-specific data to. Created lazily on first
        authenticated call rather than via a webhook, to keep the MVP
        simple (no webhook endpoint to secure and maintain).
        """
        user_id = uuid.UUID(identity.user_id)
        user = self.repository.get_by_id(user_id)
        if user is not None:
            return user

        if not identity.email:
            raise ValueError("Supabase token is missing an email claim")

        return self.repository.create(id=user_id, email=identity.email)
