"""Resolves a trading symbol to Kite's numeric instrument_token.

Kite's historical-data endpoint keys on instrument_token, not the trading
symbol (see MarketDataClient.get_historical_candles's docstring) — this is
the lookup every caller needs before it can fetch candles for a symbol.
"""

from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest


def resolve_instrument_token(client: MarketDataClient, exchange: str, tradingsymbol: str) -> int:
    for instrument in client.get_instruments(exchange):
        if instrument.get("tradingsymbol") == tradingsymbol:
            return instrument["instrument_token"]
    raise MarketDataInvalidRequest(f"No instrument_token found for {exchange}:{tradingsymbol}.")
