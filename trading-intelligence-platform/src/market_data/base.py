"""Abstract read-only market-data interface.

Per docs/CLAUDE.md section 6, Zerodha Kite Connect is a third-party API
wrapped behind this abstraction so retries, rate-limit backoff, and any
future secondary data source can be added without touching callers.

HARD RULE (docs/CLAUDE.md section 2): this interface, and every
implementation of it, may only ever define READ operations. Do not add
place_order / modify_order / cancel_order / or any other write/order
method here, behind a flag, or as a stub — there is no order-placement
code path anywhere in this codebase.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class MarketDataClient(ABC):
    """Read-only market-data source. No implementation may add order methods."""

    @abstractmethod
    def get_quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Latest last-traded-price snapshot for one or more symbols.

        symbols use Kite's "EXCHANGE:TRADINGSYMBOL" format, e.g.
        "NSE:NIFTY 50", "NSE:INDIA VIX".
        """

    @abstractmethod
    def get_historical_candles(
        self,
        instrument_token: int,
        interval: str,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        """OHLCV candles for an instrument between two timestamps.

        Kite's historical-data endpoint keys on the numeric instrument
        token, not the trading symbol — resolve the token via
        get_instruments() first (the worker pipeline caches this lookup).
        """

    @abstractmethod
    def get_instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
        """Instrument master list (symbol/token/lot-size/expiry lookup)."""
