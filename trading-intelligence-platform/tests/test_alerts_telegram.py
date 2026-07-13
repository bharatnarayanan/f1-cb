"""Tests for src/alerts/telegram.py (F6.2).

No real Telegram calls: the Bot class is mocked throughout — live delivery
against a real TELEGRAM_BOT_TOKEN hasn't been exercised in this environment
(docs/assumptions.md).
"""

from unittest.mock import AsyncMock, patch

import pytest
from telegram.error import TelegramError

from src.alerts.exceptions import AlertDeliveryError
from src.alerts.telegram import send_telegram_alert
from src.config import Settings


def _settings(**overrides) -> Settings:
    defaults = {"SECRET_KEY": "s", "DATABASE_URL": "sqlite:///:memory:"}
    defaults.update(overrides)
    return Settings(**defaults)


def test_raises_when_not_configured():
    with pytest.raises(AlertDeliveryError, match="TELEGRAM"):
        send_telegram_alert("hello", _settings())


def test_raises_when_only_token_configured():
    with pytest.raises(AlertDeliveryError):
        send_telegram_alert("hello", _settings(TELEGRAM_BOT_TOKEN="tok"))


@patch("src.alerts.telegram.Bot")
def test_sends_when_configured(mock_bot_cls):
    mock_bot_cls.return_value.send_message = AsyncMock()
    settings = _settings(TELEGRAM_BOT_TOKEN="tok", TELEGRAM_CHAT_ID="123")

    send_telegram_alert("hello", settings)

    mock_bot_cls.assert_called_once_with(token="tok")
    mock_bot_cls.return_value.send_message.assert_awaited_once_with(chat_id="123", text="hello")


@patch("src.alerts.telegram.Bot")
def test_raises_alert_delivery_error_on_telegram_error(mock_bot_cls):
    mock_bot_cls.return_value.send_message = AsyncMock(side_effect=TelegramError("boom"))
    settings = _settings(TELEGRAM_BOT_TOKEN="tok", TELEGRAM_CHAT_ID="123")

    with pytest.raises(AlertDeliveryError):
        send_telegram_alert("hello", settings)
