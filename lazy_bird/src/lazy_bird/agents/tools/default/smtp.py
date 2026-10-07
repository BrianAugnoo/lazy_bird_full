import smtplib
import ssl
from email.message import EmailMessage

from pydantic import BaseModel, ConfigDict

from lazy_bird.errors import ExternalServiceError


class ToolSettings(BaseModel):
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    sender_email: str
    model_config = ConfigDict(extra="forbid")
    
fields = {
    "smtp_password": {"default_field": True, "content": "default.basic.password", "args": {"confirm": False}},
    "sender_email": {"default_field": True, "content": "default.basic.email"},
}

class Smtp:
    """Send emails through an SMTP server configured in the tool settings."""

    def __init__(self, settings: ToolSettings):
        self.settings = settings

    def send_email(self, recipient_email: str, subject: str, body: str) -> str:
        """
        Send an email.
        
        Args:
            recipient_email: The email address of the recipient.
            subject: The subject of the email.
            body: The body content of the email.
        """
        message = EmailMessage()
        message.set_content(body)
        message["Subject"] = subject
        message["From"] = self.settings.sender_email
        message["To"] = recipient_email
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.settings.smtp_server, self.settings.smtp_port, context=context) as server:
                server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise ExternalServiceError(
                f"The email could not be sent ({error}). If the SMTP settings are wrong, tell the user to fix them on the Tools page.",
                code="smtp_failed",
            ) from error
        return f"Email sent to {recipient_email}."


tools = [Smtp]
