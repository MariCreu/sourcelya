from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str


class EmailSender(Protocol):
    """Port for outbound transactional email.

    EmailService (FASE 6) builds the actual Sourcelya templates (first
    request, reminders) and hands the rendered EmailMessage to whatever
    implements this — Resend today, anything else later without touching
    the templating or reminder logic.
    """

    def send(self, message: EmailMessage) -> None: ...
