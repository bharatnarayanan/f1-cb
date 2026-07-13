"""Claude-narrated rationale (F4.4).

Per docs/CLAUDE.md section 3: "the LLM (Claude) is used only to narrate the
reasoning tree ... It must never be the thing deciding a numeric score."
This module receives an ALREADY-COMPUTED rationale tree (from
src/engine/recommendations.py) and asks Claude to write a plain-English
paragraph explaining it — it never sends raw candles for Claude to
interpret, and never lets Claude's response override or recompute any
score.

ANTHROPIC_API_KEY is optional at the infra level (src/config.py) the same
way KITE_* is: if it's missing/placeholder, narration degrades to an
explicit placeholder string rather than blocking the whole recommendation
— a valid, fully-scored recommendation shouldn't fail just because an
optional narration layer isn't configured. This was a deliberate scope
call for this pass (confirmed with the user): the code path is real and
tested for its degraded branch, but the live Anthropic call itself hasn't
been exercised against a real key in this environment.
"""

import logging

from anthropic import Anthropic

from src.config import Settings

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL = "claude-sonnet-5"
_NOT_CONFIGURED_MESSAGE = "Narration unavailable — ANTHROPIC_API_KEY not configured."
_NARRATION_FAILED_MESSAGE = "Narration unavailable — the narration call failed; the scored recommendation above is unaffected."

_PROMPT_TEMPLATE = """You are narrating a trading setup for a NIFTY/BANKNIFTY day trader. \
You are explaining numbers that have ALREADY been computed by a deterministic scoring engine — \
you are not deciding, adjusting, or second-guessing any of them. Write 2-4 plain-English sentences \
explaining WHY this setup scored the way it did, referencing the actual factor values below. \
Do not invent data points that aren't listed. Do not give investment advice or tell the reader to \
place a trade — this is explanatory only.

Pattern: {pattern_type} ({direction}) on {symbol} {timeframe}
Confidence score: {confidence_score}/100
  Factors: {confidence_factors}
Risk score: {risk_score}/100 ({risk_reasons})
Conviction score: {conviction_score}/100
Heavyweight/sector correlation: {correlation_score}
RSI: {rsi}
Negation estimate: pattern expected to remain valid for ~{predicted_candles} candles \
(model: {model_version})
"""


def _build_prompt(symbol: str, rationale: dict) -> str:
    pattern = rationale["pattern"]
    confidence = rationale["confidence"]
    risk = rationale["risk"]
    return _PROMPT_TEMPLATE.format(
        pattern_type=pattern["type"],
        direction=pattern["direction"],
        symbol=symbol,
        timeframe=pattern["timeframe"],
        confidence_score=confidence["score"],
        confidence_factors={name: item["value"] for name, item in confidence["factors"].items()},
        risk_score=risk["score"],
        risk_reasons="; ".join(risk["reasons"]),
        conviction_score=rationale["conviction_score"],
        correlation_score=rationale["correlation"]["score"],
        rsi=rationale["rsi"],
        predicted_candles=rationale["negation"]["predicted_candles"],
        model_version=rationale["negation"]["model_version"],
    )


def narrate_rationale(symbol: str, rationale: dict, settings: Settings) -> str:
    if not settings.anthropic_api_key or settings.anthropic_api_key == "your-anthropic-api-key-here":
        return _NOT_CONFIGURED_MESSAGE

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": _build_prompt(symbol, rationale)}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception:
        logger.exception("Claude narration call failed for %s", symbol)
        return _NARRATION_FAILED_MESSAGE
