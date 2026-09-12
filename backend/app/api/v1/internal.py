import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/internal/jobs", tags=["internal"])


def verify_internal_jobs_secret(x_internal_jobs_secret: str = Header(default="")) -> None:
    """Internal endpoints are called by Supabase Cron / pg_cron, not a logged
    -in user, so they can't go through the Supabase JWT dependency. A static
    shared secret (compared with constant-time equality) is enough for the
    MVP's threat model: these endpoints are idempotent no-ops or, later,
    bounded background work — not something worth OAuth machinery for yet.
    """
    settings = get_settings()
    if not settings.internal_jobs_secret or not secrets.compare_digest(
        x_internal_jobs_secret, settings.internal_jobs_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal job credentials"
        )


@router.post("/process-reminders", dependencies=[Depends(verify_internal_jobs_secret)])
def process_reminders(db: Session = Depends(get_db)) -> dict:
    result = ReminderService(db).process_due_reminders()
    return {"reminders_sent": result.reminders_sent}
