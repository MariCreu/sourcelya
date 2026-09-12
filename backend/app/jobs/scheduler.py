"""In-process background scheduler.

Celery+Redis would be overkill for the MVP's actual load (a handful of
reminder emails and extraction retries per day). APScheduler running
inside the API process covers FASE 6/7 needs with zero extra
infrastructure. If volume ever justifies a real queue, ReminderService and
DocumentService are the only things that would need to enqueue work
elsewhere — this module is the single place that would change.
"""

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logging import get_logger

logger = get_logger(__name__)

_scheduler = BackgroundScheduler()


def start_scheduler() -> BackgroundScheduler:
    if not _scheduler.running:
        # FASE 6 registers the reminder sweep here, e.g.:
        #   _scheduler.add_job(run_reminder_sweep, "interval", hours=1)
        _scheduler.start()
        logger.info("scheduler_started")
    return _scheduler


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown()
        logger.info("scheduler_stopped")
