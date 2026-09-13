"""Reminder business logic.

Deliberately not run by an in-process scheduler (APScheduler, etc.): with
multiple API instances/workers, an in-process scheduler either duplicates
work or requires its own leader-election machinery, and it only runs while
the process happens to be alive. Instead, `POST /internal/jobs/process-reminders`
(see app/api/v1/internal.py) is a plain, idempotent HTTP endpoint that
Supabase Cron / pg_cron calls on a schedule in production, and that can be
invoked manually in development or tests.

`ComplianceRequest` exists as of FASE 3, but the reminder cadence itself
(`Settings.reminder_schedule_days`) is still FASE 6 work — this class and
its endpoint exist now purely so FASE 6 slots real logic into an
already-decided shape instead of retrofitting one.

Planned idempotency mechanism for FASE 6, so it isn't lost by the time we
get there: `ComplianceRequest` already has `reminder_count` and
`last_reminder_at` columns (added in FASE 3, unused until FASE 6 writes to
them). A reminder at schedule index `i` is due when
`reminder_count == i` and `now - sent_at >= reminder_schedule_days[i]`.
Sending the reminder and incrementing `reminder_count` must happen in the
same transaction, guarded by `WHERE reminder_count = :i`, so running this
job twice (overlapping cron invocations, a manual retry, ...) can never
send the same interval's reminder twice.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ReminderRunResult:
    reminders_sent: int


class ReminderService:
    def __init__(self, db: Session):
        self.db = db

    def process_due_reminders(self) -> ReminderRunResult:
        # Still a no-op: the cadence logic described above is FASE 6 work.
        # Trivially idempotent: calling this repeatedly does nothing, always.
        return ReminderRunResult(reminders_sent=0)
