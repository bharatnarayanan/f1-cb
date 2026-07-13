"""Tests for src/llm/narration.py (F4.4).

No real Anthropic calls: the Anthropic client is mocked throughout. Live
narration against a real ANTHROPIC_API_KEY hasn't been exercised in this
environment — see docs/CLAUDE.md section 3 / docs/assumptions.md for why
that's a deliberate scope call, not an oversight.
"""

from unittest.mock import MagicMock, patch

from src.config import Settings
from src.llm.narration import _NOT_CONFIGURED_MESSAGE, narrate_rationale


def _settings(**overrides) -> Settings:
    defaults = {"SECRET_KEY": "s", "DATABASE_URL": "sqlite:///:memory:"}
    defaults.update(overrides)
    return Settings(**defaults)


def _rationale() -> dict:
    return {
        "pattern": {"type": "engulfing", "direction": "bullish", "timeframe": "15m", "bar_ts": "2026-07-01T09:30:00"},
        "negation": {"model_version": "heuristic-v1", "predicted_candles": 3.0, "predicted_window_end": "..."},
        "correlation": {"score": 0.8, "constituents": []},
        "rsi": 60.0,
        "confidence": {"score": 75.0, "factors": {"macro_sr_alignment": {"value": 0.8}}},
        "risk": {"score": 30.0, "reasons": ["VIX regime 'normal' base risk: 20.0"]},
        "conviction_score": 65.0,
        "narrative": None,
    }


def test_returns_placeholder_when_key_not_configured():
    settings = _settings()  # ANTHROPIC_API_KEY unset -> None

    result = narrate_rationale("NSE:NIFTY 50", _rationale(), settings)

    assert result == _NOT_CONFIGURED_MESSAGE


def test_returns_placeholder_when_key_is_the_example_placeholder():
    settings = _settings(ANTHROPIC_API_KEY="your-anthropic-api-key-here")

    result = narrate_rationale("NSE:NIFTY 50", _rationale(), settings)

    assert result == _NOT_CONFIGURED_MESSAGE


@patch("src.llm.narration.Anthropic")
def test_calls_anthropic_and_returns_text_when_configured(mock_anthropic_cls):
    mock_block = MagicMock(type="text", text="This setup scored well because...")
    mock_response = MagicMock(content=[mock_block])
    mock_anthropic_cls.return_value.messages.create.return_value = mock_response
    settings = _settings(ANTHROPIC_API_KEY="real-key")

    result = narrate_rationale("NSE:NIFTY 50", _rationale(), settings)

    assert result == "This setup scored well because..."
    mock_anthropic_cls.assert_called_once_with(api_key="real-key")


@patch("src.llm.narration.Anthropic")
def test_degrades_gracefully_when_the_api_call_fails(mock_anthropic_cls):
    mock_anthropic_cls.return_value.messages.create.side_effect = RuntimeError("network error")
    settings = _settings(ANTHROPIC_API_KEY="real-key")

    result = narrate_rationale("NSE:NIFTY 50", _rationale(), settings)

    assert "unavailable" in result.lower()
