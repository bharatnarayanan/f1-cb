"""Zerodha Kite Connect implementation of MarketDataClient.

READ-ONLY. Only wraps ltp(), ohlc(), historical_data(), and instruments() —
Kite Connect's read endpoints. Do not add place_order / modify_order /
cancel_order / gtt / basket order calls here or anywhere else in this
codebase. See docs/CLAUDE.md section 2.
"""

import logging
import time
from datetime import datetime
from typing import Any

from kiteconnect import KiteConnect
from kiteconnect.exceptions import (
    InputException,
    NetworkException,
    PermissionException,
    TokenException,
)

from src.market_data.base import MarketDataClient
from src.market_data.exceptions import (
    MarketDataAuthError,
    MarketDataInvalidRequest,
    MarketDataUnavailable,
)

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 1.0


class KiteMarketDataClient(MarketDataClient):
    def __init__(self, api_key: str, access_token: str, kite: KiteConnect | None = None) -> None:
        self._kite = kite or KiteConnect(api_key=api_key)
        if kite is None:
            self._kite.set_access_token(access_token)

    def _call_with_retry(self, description: str, fn, *args, **kwargs):
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return fn(*args, **kwargs)
            except TokenException as exc:
                # Retrying won't fix an expired/invalid access token.
                logger.warning("Kite auth failed on %s: %s", description, exc)
                raise MarketDataAuthError(
                    f"Kite Connect rejected credentials during {description}. "
                    "The daily access token has likely expired — regenerate it."
                ) from exc
            except NetworkException as exc:
                last_error = exc
                logger.warning(
                    "Kite network error on %s (attempt %d/%d): %s",
                    description, attempt, _MAX_ATTEMPTS, exc,
                )
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_SECONDS * attempt)
            except (InputException, PermissionException) as exc:
                # Permanent, non-transient errors (bad symbol, insufficient
                # app scope) — retrying can never fix these, and reporting
                # them as MarketDataUnavailable (503) would mislead the
                # caller into thinking it's a transient outage worth
                # retrying.
                logger.warning("Kite rejected %s: %s", description, exc)
                raise MarketDataInvalidRequest(
                    f"Kite Connect rejected the request during {description}: {exc}"
                ) from exc
            except Exception as exc:  # DataException, GeneralException, etc.
                last_error = exc
                logger.warning(
                    "Kite error on %s (attempt %d/%d): %s",
                    description, attempt, _MAX_ATTEMPTS, exc,
                )
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_SECONDS * attempt)

        raise MarketDataUnavailable(
            f"Kite Connect call failed after {_MAX_ATTEMPTS} attempts: {description}"
        ) from last_error

    def get_quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        return self._call_with_retry("get_quote", self._kite.ltp, symbols)

    def get_historical_candles(
        self,
        instrument_token: int,
        interval: str,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        return self._call_with_retry(
            "get_historical_candles",
            self._kite.historical_data,
            instrument_token,
            from_date,
            to_date,
            interval,
        )

    def get_instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
        return self._call_with_retry("get_instruments", self._kite.instruments, exchange)
