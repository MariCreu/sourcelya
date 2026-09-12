from functools import lru_cache

from app.core.config import get_settings
from app.integrations.email.base import EmailSender
from app.integrations.email.console_email import ConsoleEmailSender
from app.integrations.email.resend_email import ResendEmailSender


@lru_cache
def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.resend_api_key:
        return ResendEmailSender(
            api_key=settings.resend_api_key, from_address=settings.email_from_address
        )
    return ConsoleEmailSender()
