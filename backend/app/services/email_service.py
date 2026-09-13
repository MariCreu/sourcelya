from app.integrations.email.base import EmailSender
from app.integrations.email.templates import (
    ComplianceRequestEmailContext,
    MissingInformationFollowUpEmailContext,
    RequestCompleteEmailContext,
    build_compliance_request_email,
    build_missing_information_follow_up_email,
    build_request_complete_email,
)


class EmailService:
    """Thin layer between the domain (ComplianceRequestService,
    FollowUpService) and the EmailSender port — keeps template
    selection/building out of the service and out of the transport
    implementation.
    """

    def __init__(self, sender: EmailSender):
        self._sender = sender

    def send_compliance_request(self, context: ComplianceRequestEmailContext) -> None:
        message = build_compliance_request_email(context)
        self._sender.send(message)

    def send_missing_information_follow_up(
        self, context: MissingInformationFollowUpEmailContext
    ) -> None:
        message = build_missing_information_follow_up_email(context)
        self._sender.send(message)

    def send_request_complete(self, context: RequestCompleteEmailContext) -> None:
        message = build_request_complete_email(context)
        self._sender.send(message)
