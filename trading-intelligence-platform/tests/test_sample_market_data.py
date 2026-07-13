"""Tests for the in-memory sample market-data client (Phase 2 default mode).

No network, no Zerodha creds — this is what DATA_MODE=sample serves.
"""

from datetime import datetime, timedelta

from src.market_data.base import MarketDataClient
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


def test_sample_client_exposes_no_order_methods():
    declared = {name for name in dir(SampleMarketDataClient) if not name.startswith("_")}
    assert not declared & FORBIDDEN_METHOD_NAMES


def test_sample_client_is_a_market_data_client():
    assert isinstance(SampleMarketDataClient(), MarketDataClient)


def test_get_quote_returns_a_plausible_nifty_price():
    client = SampleMarketDataClient(seed=42)

    quote = client.get_quote(["NSE:NIFTY 50"])

    price = quote["NSE:NIFTY 50"]["last_price"]
    assert 20000 < price < 30000


def test_get_quote_walks_deterministically_for_a_fixed_seed():
    first = SampleMarketDataClient(seed=7).get_quote(["NSE:NIFTY 50"])
    second = SampleMarketDataClient(seed=7).get_quote(["NSE:NIFTY 50"])

    assert first == second


def test_repeated_calls_produce_a_random_walk_not_a_constant():
    client = SampleMarketDataClient(seed=1)

    prices = [client.get_quote(["NSE:NIFTY 50"])["NSE:NIFTY 50"]["last_price"] for _ in range(5)]

    assert len(set(prices)) > 1


def test_get_historical_candles_covers_the_requested_window():
    client = SampleMarketDataClient(seed=3)
    frm = datetime(2026, 7, 1, 9, 15)
    to = frm + timedelta(minutes=20)

    candles = client.get_historical_candles(256265, "5minute", frm, to)

    assert len(candles) == 5
    for candle in candles:
        assert candle["low"] <= candle["open"] <= candle["high"]
        assert candle["low"] <= candle["close"] <= candle["high"]
        assert candle["volume"] > 0


def test_get_historical_candles_reflects_the_requested_instrument():
    client = SampleMarketDataClient(seed=5)
    frm = datetime(2026, 7, 1, 9, 15)
    to = frm + timedelta(minutes=5)

    nifty_candles = client.get_historical_candles(256265, "5minute", frm, to)  # NIFTY 50
    banknifty_candles = client.get_historical_candles(260105, "5minute", frm, to)  # NIFTY BANK

    # NIFTY ~24500, BANKNIFTY ~52000 — an unrecognized/ignored instrument_token
    # would return NIFTY-scale prices for both.
    assert nifty_candles[0]["close"] < 30000
    assert banknifty_candles[0]["close"] > 40000


def test_get_instruments_filters_by_exchange():
    client = SampleMarketDataClient()

    all_instruments = client.get_instruments()
    nse_only = client.get_instruments("NSE")

    assert len(all_instruments) >= 1
    assert all(i["exchange"] == "NSE" for i in nse_only)
