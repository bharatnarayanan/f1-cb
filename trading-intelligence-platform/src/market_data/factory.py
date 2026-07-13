"""Builds the read-only Kite market-data client from app settings.

Raises loudly (per docs/CLAUDE.md's fail-loud convention, mirrored in
src/config.py) rather than returning a client that will silently 401 on
first use.
"""

from functools import lru_cache

from src.config import Settings, get_settings
from src.market_data.base import MarketDataClient
from src.market_data.kite_client import KiteMarketDataClient
from src.market_data.sample_client import SampleMarketDataClient


def build_market_data_client(settings: Settings) -> MarketDataClient:
    if settings.data_mode == "sample":
        return SampleMarketDataClient()

    if not settings.kite_api_key or not settings.kite_access_token:
        raise RuntimeError(
            "DATA_MODE=live but KITE_API_KEY / KITE_ACCESS_TOKEN are not set. "
            "Copy .env.example to .env and fill in read-only Kite Connect "
            "credentials — see scripts/kite_daily_login.py — or set "
            "DATA_MODE=sample to run without them."
        )
    return KiteMarketDataClient(
        api_key=settings.kite_api_key,
        access_token=settings.kite_access_token,
    )


@lru_cache
def get_market_data_client() -> MarketDataClient:
    return build_market_data_client(get_settings())
