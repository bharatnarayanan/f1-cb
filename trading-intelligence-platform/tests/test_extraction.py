"""Tests for src/llm/extraction.py (F5.2).

No real Anthropic calls: the client is mocked throughout, same posture as
tests/test_narration.py — live extraction against a real ANTHROPIC_API_KEY
hasn't been exercised in this environment (docs/assumptions.md).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.llm.exceptions import ExtractionUnavailable
from src.llm.extraction import extract_canonical_logic


def _settings(**overrides) -> Settings:
    defaults = {"SECRET_KEY": "s", "DATABASE_URL": "sqlite:///:memory:"}
    defaults.update(overrides)
    return Settings(**defaults)


def test_raises_when_key_not_configured():
    with pytest.raises(ExtractionUnavailable, match="ANTHROPIC_API_KEY"):
        extract_canonical_logic("buy when RSI < 30", _settings())


def test_raises_when_key_is_the_example_placeholder():
    with pytest.raises(ExtractionUnavailable):
        extract_canonical_logic("buy when RSI < 30", _settings(ANTHROPIC_API_KEY="your-anthropic-api-key-here"))


@patch("src.llm.extraction.Anthropic")
def test_returns_tool_input_on_successful_call(mock_anthropic_cls):
    fake_canonical_logic = {
        "version": "1.0",
        "instrument": {"underlying": "NIFTY"},
        "timeframe": "15m",
        "entry": {"conditions": [{"left": {"field": "close"}, "operator": ">", "right": 100}]},
        "exit": {"targets": [{"type": "fixed_points", "value": 20}], "stop_loss": {"type": "fixed_points", "value": 10}},
    }
    mock_block = MagicMock(type="tool_use", name="emit_canonical_logic", input=fake_canonical_logic)
    mock_block.name = "emit_canonical_logic"
    mock_response = MagicMock(content=[mock_block])
    mock_anthropic_cls.return_value.messages.create.return_value = mock_response

    result = extract_canonical_logic("buy when close > 100", _settings(ANTHROPIC_API_KEY="real-key"))

    assert result == fake_canonical_logic


@patch("src.llm.extraction.Anthropic")
def test_raises_extraction_unavailable_when_no_tool_call_returned(mock_anthropic_cls):
    mock_text_block = MagicMock(type="text", text="I'm not sure how to extract this.")
    mock_response = MagicMock(content=[mock_text_block])
    mock_anthropic_cls.return_value.messages.create.return_value = mock_response

    with pytest.raises(ExtractionUnavailable):
        extract_canonical_logic("gibberish input", _settings(ANTHROPIC_API_KEY="real-key"))


@patch("src.llm.extraction.Anthropic")
def test_raises_extraction_unavailable_when_api_call_fails(mock_anthropic_cls):
    mock_anthropic_cls.return_value.messages.create.side_effect = RuntimeError("network error")

    with pytest.raises(ExtractionUnavailable):
        extract_canonical_logic("buy when close > 100", _settings(ANTHROPIC_API_KEY="real-key"))
