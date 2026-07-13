"""Tests for src/market_data/instruments.py."""

from unittest.mock import MagicMock

import pytest

from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.instruments import resolve_instrument_token


def test_resolves_matching_instrument_token():
    client = MagicMock()
    client.get_instruments.return_value = [
        {"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "exchange": "NSE"},
        {"instrument_token": 260105, "tradingsymbol": "NIFTY BANK", "exchange": "NSE"},
    ]

    token = resolve_instrument_token(client, "NSE", "NIFTY 50")

    assert token == 256265
    client.get_instruments.assert_called_once_with("NSE")


def test_raises_invalid_request_when_symbol_not_found():
    client = MagicMock()
    client.get_instruments.return_value = [{"instrument_token": 256265, "tradingsymbol": "NIFTY 50"}]

    with pytest.raises(MarketDataInvalidRequest):
        resolve_instrument_token(client, "NSE", "BOGUS")
