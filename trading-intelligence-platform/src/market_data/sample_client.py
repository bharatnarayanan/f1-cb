"""Deterministic-ish sample market data — no Zerodha credentials required.

Phase 2 ships in "sample data mode" by default (DATA_MODE=sample) so the
whole stack — DB, Redis, FastAPI routes — is provable end-to-end before a
real daily Kite access token exists. Prices random-walk from realistic
NIFTY/BANKNIFTY/VIX anchors; nothing here ever touches the network.

Every route that uses this client reports data_mode="sample" in its
response, per docs/CLAUDE.md section 6 ("never fire a recommendation on
stale/missing data") — sample data must never be mistaken for the real
thing downstream.

READ-ONLY, same as every other MarketDataClient implementation: no order
methods here or anywhere else. See docs/CLAUDE.md section 2.
"""

import random
from datetime import datetime, timedelta
from typing import Any

from src.market_data.base import MarketDataClient

_BASE_PRICES: dict[str, float] = {
    "NSE:NIFTY 50": 24500.0,
    "NSE:NIFTY BANK": 52000.0,
    "NSE:INDIA VIX": 13.5,
    # Heavyweight watchlist constituents (docs/assumptions.md #6) — added so
    # the F4.1 correlation engine has real sample data to demonstrate
    # against, not just the index/VIX trio Phase 2/3 needed.
    "NSE:RELIANCE": 1500.0,
    "NSE:HDFCBANK": 1650.0,
    "NSE:ICICIBANK": 1200.0,
    "NSE:INFY": 1850.0,
    "NSE:TCS": 3850.0,
    "NSE:LT": 3600.0,
    "NSE:BHARTIARTL": 1650.0,
    "NSE:ITC": 470.0,
    "NSE:KOTAKBANK": 1800.0,
    "NSE:AXISBANK": 1150.0,
    "NSE:SBIN": 830.0,
    "NSE:BAJFINANCE": 7200.0,
    "NSE:HINDUNILVR": 2400.0,
    "NSE:M&M": 2900.0,
    "NSE:SUNPHARMA": 1750.0,
    "NSE:NIFTY IT": 42000.0,
    "NSE:NIFTY FMCG": 58000.0,
    "NSE:NIFTY PHARMA": 22000.0,
    "NSE:NIFTY AUTO": 24000.0,
}
_DEFAULT_BASE_PRICE = 1000.0

# instrument_tokens below are ARBITRARY placeholders for sample mode only —
# not real Kite Connect tokens. Never use them against a live Kite session;
# DATA_MODE=live resolves real tokens via KiteMarketDataClient.get_instruments().
_SAMPLE_INSTRUMENTS: list[dict[str, Any]] = [
    {"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 260105, "tradingsymbol": "NIFTY BANK", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 264969, "tradingsymbol": "INDIA VIX", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 738561, "tradingsymbol": "RELIANCE", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 341249, "tradingsymbol": "HDFCBANK", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 1270529, "tradingsymbol": "ICICIBANK", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 408065, "tradingsymbol": "INFY", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 2953217, "tradingsymbol": "TCS", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 2939649, "tradingsymbol": "LT", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 2714625, "tradingsymbol": "BHARTIARTL", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 424961, "tradingsymbol": "ITC", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 492033, "tradingsymbol": "KOTAKBANK", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 1510401, "tradingsymbol": "AXISBANK", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 779521, "tradingsymbol": "SBIN", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 81153, "tradingsymbol": "BAJFINANCE", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 356865, "tradingsymbol": "HINDUNILVR", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 519937, "tradingsymbol": "M&M", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 857857, "tradingsymbol": "SUNPHARMA", "exchange": "NSE", "segment": "EQ"},
    {"instrument_token": 2865921, "tradingsymbol": "NIFTY IT", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 261889, "tradingsymbol": "NIFTY FMCG", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 262657, "tradingsymbol": "NIFTY PHARMA", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 263169, "tradingsymbol": "NIFTY AUTO", "exchange": "NSE", "segment": "INDICES"},
]

# instrument_token -> base price, so get_historical_candles() reflects the
# actual requested instrument instead of always defaulting to NIFTY 50's
# scale. Unrecognized tokens fall back to _DEFAULT_BASE_PRICE.
_TOKEN_BASE_PRICES: dict[int, float] = {
    instrument["instrument_token"]: _BASE_PRICES.get(
        f"{instrument['exchange']}:{instrument['tradingsymbol']}", _DEFAULT_BASE_PRICE
    )
    for instrument in _SAMPLE_INSTRUMENTS
}


class SampleMarketDataClient(MarketDataClient):
    """In-memory random-walk market data. Never used against real capital."""

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)
        self._last_price: dict[str, float] = dict(_BASE_PRICES)

    def _walk(self, symbol: str) -> float:
        base = self._last_price.get(symbol, _DEFAULT_BASE_PRICE)
        pct_move = self._random.uniform(-0.0015, 0.0015)
        new_price = round(base * (1 + pct_move), 2)
        self._last_price[symbol] = new_price
        return new_price

    def get_quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        return {symbol: {"last_price": self._walk(symbol)} for symbol in symbols}

    def get_historical_candles(
        self,
        instrument_token: int,
        interval: str,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        candles = []
        cursor = from_date
        step = timedelta(minutes=5)
        base = _TOKEN_BASE_PRICES.get(instrument_token, _DEFAULT_BASE_PRICE)
        while cursor <= to_date:
            open_ = base * (1 + self._random.uniform(-0.002, 0.002))
            close = open_ * (1 + self._random.uniform(-0.002, 0.002))
            high = max(open_, close) * (1 + self._random.uniform(0, 0.001))
            low = min(open_, close) * (1 - self._random.uniform(0, 0.001))
            candles.append(
                {
                    "date": cursor,
                    "open": round(open_, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": self._random.randint(10_000, 500_000),
                }
            )
            base = close
            cursor += step
        return candles

    def get_instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
        if exchange is None:
            return list(_SAMPLE_INSTRUMENTS)
        return [i for i in _SAMPLE_INSTRUMENTS if i["exchange"] == exchange]
