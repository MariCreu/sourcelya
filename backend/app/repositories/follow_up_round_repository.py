import uuid

from sqlalchemy import select

from app.models.follow_up_round import FollowUpRound
from app.repositories.base import CompanyScopedRepository


class FollowUpRoundRepository(CompanyScopedRepository[FollowUpRound]):
    model = FollowUpRound

    def list_for_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> list[FollowUpRound]:
        stmt = (
            select(FollowUpRound)
            .where(FollowUpRound.company_id == company_id, FollowUpRound.request_id == request_id)
            .order_by(FollowUpRound.round_number)
        )
        return list(self.db.scalars(stmt).all())

    def latest_for_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> FollowUpRound | None:
        rounds = self.list_for_request(company_id, request_id)
        return rounds[-1] if rounds else None
