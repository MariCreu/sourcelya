import resend

from app.integrations.email.base import EmailMessage, EmailSender


class ResendEmailSender(EmailSender):
    def __init__(self, api_key: str, from_address: str):
        resend.api_key = api_key
        self._from_address = from_address

    def send(self, message: EmailMessage) -> None:
        resend.Emails.send(
            {
                "from": self._from_address,
                "to": [message.to],
                "subject": message.subject,
                "html": message.html_body,
            }
        )
