"""Tests for src/alerts/email.py (F6.2).

No real SMTP calls: smtplib.SMTP is mocked throughout — live delivery
against a real SMTP account hasn't been exercised in this environment
(docs/assumptions.md).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.alerts.email import send_email_alert
from src.alerts.exceptions import AlertDeliveryError
from src.config import Settings


def _settings(**overrides) -> Settings:
    defaults = {"SECRET_KEY": "s", "DATABASE_URL": "sqlite:///:memory:"}
    defaults.update(overrides)
    return Settings(**defaults)


def test_raises_when_not_configured():
    with pytest.raises(AlertDeliveryError, match="SMTP"):
        send_email_alert("subject", "body", _settings())


def test_raises_when_partially_configured():
    settings = _settings(SMTP_HOST="smtp.example.com", SMTP_USER="user")
    with pytest.raises(AlertDeliveryError):
        send_email_alert("subject", "body", settings)


@patch("src.alerts.email.smtplib.SMTP")
def test_sends_when_fully_configured(mock_smtp_cls):
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server
    settings = _settings(
        SMTP_HOST="smtp.example.com", SMTP_USER="user@example.com", SMTP_PASSWORD="pw", ALERT_EMAIL_TO="me@example.com"
    )

    send_email_alert("subject", "body", settings)

    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@example.com", "pw")
    mock_server.send_message.assert_called_once()


@patch("src.alerts.email.smtplib.SMTP")
def test_raises_alert_delivery_error_when_send_fails(mock_smtp_cls):
    mock_smtp_cls.side_effect = OSError("connection refused")
    settings = _settings(
        SMTP_HOST="smtp.example.com", SMTP_USER="user@example.com", SMTP_PASSWORD="pw", ALERT_EMAIL_TO="me@example.com"
    )

    with pytest.raises(AlertDeliveryError):
        send_email_alert("subject", "body", settings)
