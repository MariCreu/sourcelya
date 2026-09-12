from app.core.logging import get_logger
from app.integrations.email.base import EmailMessage, EmailSender

logger = get_logger(__name__)


class ConsoleEmailSender(EmailSender):
    """Used when no RESEND_API_KEY is configured (local dev, tests).

    Logs the email instead of sending it so the request/reminder flow can
    be exercised end-to-end without a real provider.
    """

    def send(self, message: EmailMessage) -> None:
        logger.info("email_not_sent_no_provider", to=message.to, subject=message.subject)
