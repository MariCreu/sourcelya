"""Reminder business logic — distinct from a follow-up (FASE 6):

- **FOLLOW-UP** (`FollowUpService`): Sourcelya knows specifically what
  information is still missing and asks for exactly that.
- **REMINDER** (this service): something was already asked (the initial
  request, or the current follow-up round) and the supplier simply hasn't
  responded in a while. A reminder never changes *what* is being asked —
  it re-delivers the same content via a freshly minted link (see
  `FollowUpService.send_reminder`) and never creates a new `FollowUpRound`.

Not run by an in-process scheduler — see the root README's "Why not an
in-process scheduler for jobs". `POST /internal/jobs/process-reminders`
(`app/api/v1/internal.py`) is the plain, idempotent HTTP endpoint Supabase
Cron / pg_cron calls on a schedule in production.

Idempotency: a reminder at schedule index `i` is due when
`reminder_count == i` and `now - last_outbound_at >= reminder_schedule_days[i]`
(`last_outbound_at` is the latest follow-up round's `created_at`, or
`sent_at` if there's no round yet). The increment is guarded by an
UPDATE ... WHERE reminder_count = :i, so two overlapping cron invocations
(or a manual retry) can never send the same interval's reminder twice —
one of them updates 0 rows and skips sending.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.domain.enums import RequestStatus
from app.models.compliance_request import ComplianceRequest
from app.repositories.company_repository import CompanyRepository
from app.repositories.follow_up_round_repository import FollowUpRoundRepository
from app.services.email_service import EmailService
from app.services.follow_up_service import FollowUpService

_ACTIVE_STATUSES = (
    RequestStatus.SENT.value,
    RequestStatus.OPENED.value,
    RequestStatus.IN_PROGRESS.value,
    RequestStatus.SUBMITTED.value,
)


@dataclass(frozen=True)
class ReminderRunResult:
    reminders_sent: int


class ReminderService:
    def __init__(self, db: Session, email_service: EmailService, settings: Settings | None = None):
        self.db = db
        self.email_service = email_service
        self.settings = settings or get_settings()
        self.round_repository = FollowUpRoundRepository(self.db)

    def _candidates(self) -> list[ComplianceRequest]:
        stmt = select(ComplianceRequest).where(
            ComplianceRequest.status.in_(_ACTIVE_STATUSES),
            ComplianceRequest.token_revoked_at.is_(None),
        )
        return list(self.db.scalars(stmt).all())

    def _last_outbound_at(self, request: ComplianceRequest) -> datetime | None:
        latest_round = self.round_repository.latest_for_request(request.company_id, request.id)
        if latest_round is not None:
            return latest_round.created_at
        return request.sent_at

    def _is_due(self, request: ComplianceRequest) -> bool:
        schedule = self.settings.reminder_schedule_days
        if request.reminder_count >= len(schedule):
            return False
        anchor = self._last_outbound_at(request)
        if anchor is None:
            return False
        days_required = schedule[request.reminder_count]
        return datetime.now(timezone.utc) - anchor >= timedelta(days=days_required)

    def process_due_reminders(self) -> ReminderRunResult:
        sent = 0
        for request in self._candidates():
            if not self._is_due(request):
                continue

            # Idempotency guard: claim this reminder slot before sending
            # anything. If another (overlapping) run already claimed it,
            # rowcount is 0 and we skip — never send the same interval's
            # reminder twice.
            claimed = self.db.execute(
                update(ComplianceRequest)
                .where(
                    ComplianceRequest.id == request.id,
                    ComplianceRequest.reminder_count == request.reminder_count,
                )
                .values(
                    reminder_count=request.reminder_count + 1,
                    last_reminder_at=datetime.now(timezone.utc),
                )
            )
            self.db.flush()
            if claimed.rowcount == 0:
                continue

            company = CompanyRepository(self.db).get_by_id(request.company_id)
            self.db.refresh(request)
            FollowUpService(self.db, self.email_service, self.settings).send_reminder(
                company, request
            )
            sent += 1
        return ReminderRunResult(reminders_sent=sent)
