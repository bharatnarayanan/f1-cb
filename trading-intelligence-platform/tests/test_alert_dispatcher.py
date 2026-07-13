"""Tests for src/alerts/dispatcher.py (F6.2)."""

import uuid
from unittest.mock import MagicMock, patch

from src.alerts.dispatcher import dispatch_alerts
from src.alerts.exceptions import AlertDeliveryError
from src.config import Settings
from src.db.models import Recommendation


def _settings() -> Settings:
    return Settings(SECRET_KEY="s", DATABASE_URL="sqlite:///:memory:")


def _recommendation() -> Recommendation:
    return Recommendation(
        id=uuid.uuid4(), category="tactical", symbol="NSE:NIFTY 50", action="BUY_CE",
        confidence_score=70.0, risk_score=20.0, conviction_score=63.0,
        rationale={}, vix_regime_at_creation="normal",
    )


@patch("src.alerts.dispatcher.send_email_alert")
@patch("src.alerts.dispatcher.send_telegram_alert")
def test_dispatch_records_failed_when_channels_not_configured(mock_telegram, mock_email):
    mock_telegram.side_effect = AlertDeliveryError("not configured")
    mock_email.side_effect = AlertDeliveryError("not configured")
    db = MagicMock()

    logs = dispatch_alerts(_recommendation(), db, _settings())

    statuses = {log.channel: log.dispatch_status for log in logs}
    assert statuses["telegram"] == "failed"
    assert statuses["email"] == "failed"
    assert statuses["dashboard"] == "sent"  # always sent — logging IS its delivery
    assert db.add.call_count == 3


@patch("src.alerts.dispatcher.send_email_alert")
@patch("src.alerts.dispatcher.send_telegram_alert")
def test_dispatch_records_sent_when_delivery_succeeds(mock_telegram, mock_email):
    mock_telegram.return_value = None
    mock_email.return_value = None
    db = MagicMock()

    logs = dispatch_alerts(_recommendation(), db, _settings())

    statuses = {log.channel: log.dispatch_status for log in logs}
    assert statuses["telegram"] == "sent"
    assert statuses["email"] == "sent"
    assert all(log.sent_at is not None for log in logs)


@patch("src.alerts.dispatcher.send_email_alert")
@patch("src.alerts.dispatcher.send_telegram_alert")
def test_dispatch_never_raises_even_when_all_channels_fail(mock_telegram, mock_email):
    mock_telegram.side_effect = AlertDeliveryError("boom")
    mock_email.side_effect = AlertDeliveryError("boom")
    db = MagicMock()

    logs = dispatch_alerts(_recommendation(), db, _settings())  # must not raise

    assert len(logs) == 3
    assert all(log.recommendation_id for log in logs)
