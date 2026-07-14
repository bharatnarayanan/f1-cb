"""Unified alert dispatch (F6.2) — fires a recommendation alert across
every channel and writes one alerts_log row per channel, honestly
recording dispatch_status ("sent" only if delivery actually succeeded,
"failed" otherwise — never faked, docs/CLAUDE.md section 6). "dashboard"
has no real destination yet (no frontend exists — Phase 7); it's recorded
as sent immediately since writing the alerts_log row IS the dashboard's
future data source, not a placeholder for a channel that doesn't exist.

Caller (src/routes/recommendations.py) is responsible for committing —
this only adds AlertLog rows to the session, same pattern as the
Recommendation row itself.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.alerts.email import send_email_alert
from src.alerts.exceptions import AlertDeliveryError
from src.alerts.telegram import send_telegram_alert
from src.config import Settings
from src.db.models import AlertLog, Recommendation
from src.metrics import alerts_dispatched_total

logger = logging.getLogger(__name__)


def _format_message(recommendation: Recommendation) -> str:
    return (
        f"[{recommendation.category.upper()}] {recommendation.symbol} — {recommendation.action}\n"
        f"Confidence: {recommendation.confidence_score} | Risk: {recommendation.risk_score} | "
        f"Conviction: {recommendation.conviction_score}\n"
        "Informational only — no order was placed. Review and execute manually if you choose to."
    )


def dispatch_alerts(recommendation: Recommendation, db: Session, settings: Settings) -> list[AlertLog]:
    message = _format_message(recommendation)
    logs: list[AlertLog] = []

    telegram_log = AlertLog(recommendation_id=recommendation.id, channel="telegram", dispatch_status="failed")
    try:
        send_telegram_alert(message, settings)
        telegram_log.dispatch_status = "sent"
        telegram_log.sent_at = datetime.now(timezone.utc)
    except AlertDeliveryError as exc:
        logger.info("Telegram alert not sent: %s", exc)
    logs.append(telegram_log)

    email_log = AlertLog(recommendation_id=recommendation.id, channel="email", dispatch_status="failed")
    try:
        send_email_alert(f"New {recommendation.category} recommendation: {recommendation.symbol}", message, settings)
        email_log.dispatch_status = "sent"
        email_log.sent_at = datetime.now(timezone.utc)
    except AlertDeliveryError as exc:
        logger.info("Email alert not sent: %s", exc)
    logs.append(email_log)

    logs.append(
        AlertLog(
            recommendation_id=recommendation.id,
            channel="dashboard",
            dispatch_status="sent",
            sent_at=datetime.now(timezone.utc),
        )
    )

    for log in logs:
        db.add(log)
        alerts_dispatched_total.labels(channel=log.channel, status=log.dispatch_status).inc()
    return logs
