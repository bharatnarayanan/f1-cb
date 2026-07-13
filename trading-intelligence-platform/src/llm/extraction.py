"""Strategy extraction via Claude (F5.2).

Maps a submitted strategy's raw input (free text, pseudocode, or Pine
Script) onto docs/strategy_schema.json's fixed vocabulary, via a
tool-forced call so Claude can only emit the declared schema shape —
docs/CLAUDE.md section 3: the LLM extracts, it never gets to run arbitrary
logic. The tool's input_schema deliberately avoids $ref/$defs (inlined
everywhere instead) — Anthropic's tool-use JSON Schema support for $ref is
inconsistent, so this is written in the flat form their docs recommend.

Same posture as src/llm/narration.py: built and unit-tested against a
mocked Anthropic client, not exercised against a real ANTHROPIC_API_KEY in
this environment (docs/assumptions.md). Unlike narration, a missing key or
a failed call here raises ExtractionUnavailable rather than degrading to a
placeholder — canonical_logic has no honest "unknown" stand-in the way one
optional paragraph did.
"""

import logging

from anthropic import Anthropic

from src.config import Settings
from src.llm.exceptions import ExtractionUnavailable

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL = "claude-sonnet-5"
_TOOL_NAME = "emit_canonical_logic"

_OPERAND_SCHEMA = {
    "type": "object",
    "description": "A price field, a bound indicator, or a literal number.",
    "properties": {
        "field": {"type": "string", "enum": ["open", "high", "low", "close", "volume"]},
        "indicator": {"type": "string", "enum": ["RSI", "SMA", "EMA", "MACD", "VWAP", "SUPERTREND"]},
        "period": {"type": "integer"},
        "params": {"type": "object"},
        "literal": {"type": "number", "description": "Set only when this operand is a plain number."},
    },
}


def _condition_schema() -> dict:
    return {
        "type": "object",
        "required": ["left", "operator", "right"],
        "properties": {
            "left": _OPERAND_SCHEMA,
            "operator": {"type": "string", "enum": ["<", "<=", ">", ">=", "==", "!="]},
            "right": _OPERAND_SCHEMA,
        },
    }


_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Emit the strategy's structured canonical_logic per docs/strategy_schema.json. "
    "Only use the fields/indicators/operators listed in this schema — never invent new ones.",
    "input_schema": {
        "type": "object",
        "required": ["version", "instrument", "timeframe", "entry", "exit"],
        "properties": {
            "version": {"type": "string", "const": "1.0"},
            "instrument": {
                "type": "object",
                "required": ["underlying"],
                "properties": {
                    "underlying": {"type": "string", "enum": ["NIFTY", "BANKNIFTY"]},
                    "leg": {"type": "string", "enum": ["CE", "PE", "either"]},
                    "moneyness": {"type": "string", "enum": ["ITM", "ATM", "OTM"]},
                    "price_band": {
                        "type": "object",
                        "properties": {"min": {"type": "number"}, "max": {"type": "number"}},
                    },
                },
            },
            "timeframe": {"type": "string", "enum": ["1m", "5m", "10m", "15m", "30m", "1h", "2h", "3h", "1d"]},
            "pattern_trigger": {
                "type": "object",
                "properties": {
                    "pattern_type": {
                        "type": "string",
                        "enum": ["engulfing", "three_inside", "three_outside", "harami", "doji", "pin_bar", "none"],
                    },
                    "breakout_offset_points": {"type": "number"},
                },
            },
            "time_filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["rule"],
                    "properties": {
                        "rule": {"type": "string", "enum": ["ignore_before", "require_after", "retry_window"]},
                        "time": {"type": "string"},
                        "note": {"type": "string"},
                    },
                },
            },
            "entry": {
                "type": "object",
                "required": ["conditions"],
                "properties": {
                    "conditions": {"type": "array", "minItems": 1, "items": _condition_schema()},
                    "logic": {"type": "string", "enum": ["AND", "OR"]},
                    "retracement_reference": {"type": "string", "enum": ["vwap_option", "vwap_spot", "none"]},
                },
            },
            "exit": {
                "type": "object",
                "required": ["targets", "stop_loss"],
                "properties": {
                    "targets": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "prior_candle_high", "prior_candle_low", "day_high", "day_low",
                                        "supertrend_line", "sr_level", "fixed_points",
                                    ],
                                },
                                "value": {"type": "number"},
                            },
                        },
                    },
                    "stop_loss": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["below_ma", "below_vwap", "above_ma", "above_vwap", "fixed_points"],
                            },
                            "reference_indicator": _OPERAND_SCHEMA,
                            "value": {"type": "number"},
                        },
                    },
                },
            },
            "guards": {"type": "array", "items": _condition_schema()},
        },
    },
}

_SYSTEM_PROMPT = (
    "You extract trading strategy descriptions into a fixed structured schema. "
    "You NEVER invent indicators, fields, or operators outside the ones the tool schema allows. "
    "If the input doesn't specify something (e.g. no explicit stop-loss), make the most conservative "
    "reasonable choice and note it isn't explicit in the source — you are not deciding whether this "
    "strategy is good, only translating what it describes into the fixed schema."
)


def extract_canonical_logic(raw_input: str, settings: Settings) -> dict:
    if not settings.anthropic_api_key or settings.anthropic_api_key == "your-anthropic-api-key-here":
        raise ExtractionUnavailable("ANTHROPIC_API_KEY is not configured — strategy extraction needs a real key.")

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": raw_input}],
        )
    except Exception as exc:
        logger.exception("Claude extraction call failed")
        raise ExtractionUnavailable(f"Extraction call failed: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use" and block.name == _TOOL_NAME:
            return block.input

    raise ExtractionUnavailable("Claude did not return a canonical_logic tool call.")
