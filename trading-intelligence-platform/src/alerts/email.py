"""SMTP email alert sender (F6.2) — stdlib smtplib/email only, no extra
dependency. Same fail-loud-but-not-fatal posture as src/alerts/telegram.py:
missing config or a failed send raises AlertDeliveryError, caught by
src/alerts/dispatcher.py. Not exercised against a real SMTP account in this
environment (docs/assumptions.md).
"""

import logging
import smtplib
from email.message import EmailMessage

from src.alerts.exceptions import AlertDeliveryError
from src.config import Settings

logger = logging.getLogger(__name__)


def send_email_alert(subject: str, body: str, settings: Settings) -> None:
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, settings.alert_email_to]):
        raise AlertDeliveryError("SMTP_HOST / SMTP_USER / SMTP_PASSWORD / ALERT_EMAIL_TO not fully configured.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_user
    message["To"] = settings.alert_email_to
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except Exception as exc:
        logger.exception("Email send failed")
        raise AlertDeliveryError(f"Email send failed: {exc}") from exc
