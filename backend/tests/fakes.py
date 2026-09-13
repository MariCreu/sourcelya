from app.integrations.email.base import EmailMessage, EmailSender


class RecordingEmailSender(EmailSender):
    """Test double: never talks to a real provider, just remembers every
    message so a test can assert on subject/body/recipient — e.g. pulling
    the request URL out of a sent email the way a real supplier would.
    """

    def __init__(self):
        self.sent_messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent_messages.append(message)
