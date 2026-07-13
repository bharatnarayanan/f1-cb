"""Tests for the read-only Kite market-data layer (src/market_data/).

No real network calls: the underlying kiteconnect.KiteConnect client is
mocked throughout. scripts/test_kite_connection.py remains the tool for a
real, manual, read-only connectivity check against live Zerodha creds.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from kiteconnect.exceptions import InputException, NetworkException, PermissionException, TokenException

from src.market_data.base import MarketDataClient
from src.market_data.exceptions import (
    MarketDataAuthError,
    MarketDataInvalidRequest,
    MarketDataUnavailable,
)
from src.market_data.factory import build_market_data_client
from src.market_data.kite_client import KiteMarketDataClient
from src.market_data.sample_client import SampleMarketDataClient

FORBIDDEN_METHOD_NAMES = {
    "place_order",
    "modify_order",
    "cancel_order",
    "exit_order",
    "place_gtt",
    "modify_gtt",
    "delete_gtt",
    "place_mf_order",
    "cancel_mf_order",
    "place_basket_order",
}


def _client_with_mock_kite() -> tuple[KiteMarketDataClient, MagicMock]:
    mock_kite = MagicMock()
    client = KiteMarketDataClient(api_key="x", access_token="y", kite=mock_kite)
    return client, mock_kite


def test_interface_defines_no_order_methods():
    declared = set(vars(MarketDataClient))
    assert not declared & FORBIDDEN_METHOD_NAMES


def test_kite_client_exposes_no_order_methods():
    declared = {name for name in dir(KiteMarketDataClient) if not name.startswith("_")}
    assert not declared & FORBIDDEN_METHOD_NAMES


def test_get_quote_passes_through_on_success():
    client, mock_kite = _client_with_mock_kite()
    mock_kite.ltp.return_value = {"NSE:NIFTY 50": {"last_price": 24500.1}}

    result = client.get_quote(["NSE:NIFTY 50"])

    assert result == {"NSE:NIFTY 50": {"last_price": 24500.1}}
    mock_kite.ltp.assert_called_once_with(["NSE:NIFTY 50"])


def test_get_historical_candles_passes_through():
    client, mock_kite = _client_with_mock_kite()
    mock_kite.historical_data.return_value = [{"close": 100.0}]
    frm, to = datetime(2026, 7, 1), datetime(2026, 7, 8)

    result = client.get_historical_candles(256265, "5minute", frm, to)

    assert result == [{"close": 100.0}]
    mock_kite.historical_data.assert_called_once_with(256265, frm, to, "5minute")


def test_get_instruments_passes_through():
    client, mock_kite = _client_with_mock_kite()
    mock_kite.instruments.return_value = [{"tradingsymbol": "NIFTY50"}]

    result = client.get_instruments("NSE")

    assert result == [{"tradingsymbol": "NIFTY50"}]
    mock_kite.instruments.assert_called_once_with("NSE")


@patch("src.market_data.kite_client.time.sleep")
def test_network_error_retries_then_raises_unavailable(mock_sleep):
    client, mock_kite = _client_with_mock_kite()
    mock_kite.ltp.side_effect = NetworkException("timed out")

    with pytest.raises(MarketDataUnavailable):
        client.get_quote(["NSE:NIFTY 50"])

    assert mock_kite.ltp.call_count == 3


@patch("src.market_data.kite_client.time.sleep")
def test_transient_error_recovers_within_retry_budget(mock_sleep):
    client, mock_kite = _client_with_mock_kite()
    mock_kite.ltp.side_effect = [
        NetworkException("timed out"),
        {"NSE:NIFTY 50": {"last_price": 24500.1}},
    ]

    result = client.get_quote(["NSE:NIFTY 50"])

    assert result == {"NSE:NIFTY 50": {"last_price": 24500.1}}
    assert mock_kite.ltp.call_count == 2


def test_input_exception_raises_invalid_request_without_retry():
    client, mock_kite = _client_with_mock_kite()
    mock_kite.ltp.side_effect = InputException("unknown symbol")

    with pytest.raises(MarketDataInvalidRequest):
        client.get_quote(["NSE:BOGUS"])

    # A bad symbol is a permanent error — retrying identically can never
    # succeed, so it must not be retried like a NetworkException.
    mock_kite.ltp.assert_called_once()


def test_permission_exception_raises_invalid_request_without_retry():
    client, mock_kite = _client_with_mock_kite()
    mock_kite.ltp.side_effect = PermissionException("insufficient app permissions")

    with pytest.raises(MarketDataInvalidRequest):
        client.get_quote(["NSE:NIFTY 50"])

    mock_kite.ltp.assert_called_once()


def test_token_exception_raises_auth_error_without_retry():
    client, mock_kite = _client_with_mock_kite()
    mock_kite.ltp.side_effect = TokenException("invalid access token")

    with pytest.raises(MarketDataAuthError):
        client.get_quote(["NSE:NIFTY 50"])

    mock_kite.ltp.assert_called_once()


def test_factory_raises_clear_error_when_live_mode_missing_credentials():
    settings = MagicMock(data_mode="live", kite_api_key=None, kite_access_token=None)

    with pytest.raises(RuntimeError, match="KITE_API_KEY"):
        build_market_data_client(settings)


def test_factory_returns_sample_client_by_default_without_credentials():
    settings = MagicMock(data_mode="sample", kite_api_key=None, kite_access_token=None)

    client = build_market_data_client(settings)

    assert isinstance(client, SampleMarketDataClient)
