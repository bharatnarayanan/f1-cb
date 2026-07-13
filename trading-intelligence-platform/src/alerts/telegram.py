"""Telegram alert sender (F6.2).

Sends via python-telegram-bot; wrapped with asyncio.run() since v20+ is
fully async and this codebase's routes are synchronous (see
requirements.txt's comment on the pin).

Same fail-loud-but-not-fatal posture as src/llm/narration.py: a missing
TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or a failed send raises
AlertDeliveryError, which src/alerts/dispatcher.py catches and records as a
failed dispatch — a recommendation still gets created even if nobody's
listening on Telegram. Not exercised against a real bot token in this
environment (docs/assumptions.md), same posture as Claude narration/
extraction and live Kite mode.
"""

import asyncio
import logging

from telegram import Bot
from telegram.error import TelegramError

from src.alerts.exceptions import AlertDeliveryError
from src.config import Settings

logger = logging.getLogger(__name__)


async def _send(message: str, bot_token: str, chat_id: str) -> None:
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)


def send_telegram_alert(message: str, settings: Settings) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise AlertDeliveryError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not configured.")

    try:
        asyncio.run(_send(message, settings.telegram_bot_token, settings.telegram_chat_id))
    except TelegramError as exc:
        logger.exception("Telegram send failed")
        raise AlertDeliveryError(f"Telegram send failed: {exc}") from exc
