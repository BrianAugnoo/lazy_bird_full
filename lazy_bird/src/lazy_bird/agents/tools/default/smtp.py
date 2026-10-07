import smtplib
import ssl
from email.message import EmailMessage
from pydantic import BaseModel, ConfigDict

class ToolSettings(BaseModel):
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    sender_email: str
    model_config = ConfigDict(extra="forbid")
    
fields = {
    "smtp_password": {"default_field": True, "content": "default.basic.password", "args": {"confirm": False}},
    "sender_email": {"default_field": True, "content": "default.basic.email"} # or args: None
}

class Smtp:
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
        try:
            message = EmailMessage()
            message.set_content(body)
            message['Subject'] = subject
            message['From'] = self.settings.sender_email
            message['To'] = recipient_email
    
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.settings.smtp_server, self.settings.smtp_port, context=context) as server:
                server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)
            return f"Email sent successfully to {recipient_email}."
        except Exception as e:
            return f"Failed to send email, error: {e}, if the error is related to SMTP internal configuration, please inform the user."
        
tools = [Smtp]