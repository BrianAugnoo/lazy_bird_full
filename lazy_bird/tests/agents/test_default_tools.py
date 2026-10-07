"""Tools shipped in agents/tools/default/."""

from types import SimpleNamespace

import pytest

from lazy_bird.agents.tools.default import knowledge_base, smtp
from lazy_bird.errors import ExternalServiceError

SETTINGS = smtp.ToolSettings(smtp_server="mail.test", smtp_port=465, smtp_username="me", smtp_password="secret", sender_email="me@test.org")


def test_emails_are_sent_with_the_configured_account(monkeypatch):
    sent = {}

    class FakeServer:
        def __init__(self, host, port, context=None):
            sent["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr(smtp.smtplib, "SMTP_SSL", FakeServer)

    answer = smtp.Smtp(SETTINGS).send_email("you@test.org", "Hello", "The report is ready.")

    assert answer == "Email sent to you@test.org."
    assert sent["server"] == ("mail.test", 465) and sent["login"] == ("me", "secret")
    message = sent["message"]
    assert (message["From"], message["To"], message["Subject"]) == ("me@test.org", "you@test.org", "Hello")
    assert message.get_content().strip() == "The report is ready."


def test_smtp_failures_are_reported_as_tool_errors(monkeypatch):
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(smtp.smtplib, "SMTP_SSL", refuse)

    with pytest.raises(ExternalServiceError) as error:
        smtp.Smtp(SETTINGS).send_email("you@test.org", "Hello", "Body")

    assert error.value.code == "smtp_failed"
    assert "connection refused" in error.value.message


def test_the_knowledge_base_tool_returns_passages_with_their_source(monkeypatch):
    asked = []
    result = SimpleNamespace(file_name="falcon.md", chunk=SimpleNamespace(start_line=3, end_line=4, content="The battery lasts 41 days."), distance=0.12)
    monkeypatch.setattr(knowledge_base, "search", lambda query, top_k: asked.append((query, top_k)) or [result])

    answer = knowledge_base.search_knowledge_base("battery life", top_k=2)

    assert asked == [("battery life", 2)]
    assert '"file": "falcon.md"' in answer and "41 days" in answer and '"distance": 0.12' in answer
