"""Exceptions for the market-data layer.

Per docs/CLAUDE.md section 6: never let a caller silently treat a failed
fetch as valid data. Every failure surfaces as one of these, so callers
(routes, and later the worker pipeline) can skip the evaluation cycle
instead of scoring on missing/stale data.
"""


class MarketDataError(Exception):
    """Base class for all market-data-layer failures."""


class MarketDataUnavailable(MarketDataError):
    """Raised after retries are exhausted talking to the upstream data source."""


class MarketDataAuthError(MarketDataError):
    """Raised when the upstream data source rejects our credentials.

    Distinct from MarketDataUnavailable because retrying won't help — this
    means the daily Kite Connect access token has expired or is wrong.
    """


class MarketDataInvalidRequest(MarketDataError):
    """Raised when the upstream data source rejects the request itself.

    Distinct from MarketDataAuthError (bad credentials) and
    MarketDataUnavailable (transient outage) — this means the request was
    permanently malformed (e.g. an unknown symbol) or our app lacks
    permission for it. Retrying identically will never succeed.
    """
