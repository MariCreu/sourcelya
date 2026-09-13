from app.integrations.email.base import EmailSender
from app.integrations.email.templates import (
    ComplianceRequestEmailContext,
    build_compliance_request_email,
)


class EmailService:
    """Thin layer between the domain (ComplianceRequestService) and the
    EmailSender port — keeps template selection/building out of the
    service and out of the transport implementation.
    """

    def __init__(self, sender: EmailSender):
        self._sender = sender

    def send_compliance_request(self, context: ComplianceRequestEmailContext) -> None:
        message = build_compliance_request_email(context)
        self._sender.send(message)
