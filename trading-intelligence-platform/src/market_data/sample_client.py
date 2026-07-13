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
    "NSE:RELIANCE": 2950.0,
    "NSE:HDFCBANK": 1650.0,
    "NSE:ICICIBANK": 1200.0,
    "NSE:INFY": 1850.0,
    "NSE:TCS": 3850.0,
}
_DEFAULT_BASE_PRICE = 1000.0

_SAMPLE_INSTRUMENTS: list[dict[str, Any]] = [
    {"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 260105, "tradingsymbol": "NIFTY BANK", "exchange": "NSE", "segment": "INDICES"},
    {"instrument_token": 264969, "tradingsymbol": "INDIA VIX", "exchange": "NSE", "segment": "INDICES"},
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
