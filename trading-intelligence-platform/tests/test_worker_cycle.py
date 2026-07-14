"""Tests for src/worker/main.py's run_one_cycle (Phase 8, worker service
pass) — verifies the cycle iterates every active symbol/timeframe pair and
that one symbol's failure doesn't abort the rest of the watchlist.
"""

from unittest.mock import MagicMock, patch

from src.worker.main import SCAN_TIMEFRAMES, run_one_cycle


def test_calls_generate_recommendation_for_every_symbol_and_timeframe():
    with patch("src.worker.main._active_watchlist_symbols", return_value=["RELIANCE", "NIFTY BANK"]), \
         patch("src.worker.main.get_settings", return_value=MagicMock()), \
         patch("src.worker.main.get_session_factory", return_value=MagicMock(side_effect=lambda: MagicMock())), \
         patch("src.worker.main.get_market_data_client", return_value=MagicMock()), \
         patch("src.worker.main.get_redis_cache", return_value=MagicMock()), \
         patch("src.worker.main.generate_recommendation", return_value={"recommendation": None, "message": "no pattern"}) as mock_generate:
        run_one_cycle()

    called_pairs = {(c.kwargs["symbol"], c.kwargs["timeframe"]) for c in mock_generate.call_args_list}
    expected_pairs = {(symbol, tf) for symbol in ["RELIANCE", "NIFTY BANK"] for tf in SCAN_TIMEFRAMES}
    assert called_pairs == expected_pairs


def test_one_symbol_raising_does_not_abort_the_rest_of_the_cycle():
    def _flaky_generate(symbol, **kwargs):
        if symbol == "RELIANCE":
            raise RuntimeError("simulated data glitch")
        return {"recommendation": None, "message": "no pattern"}

    with patch("src.worker.main._active_watchlist_symbols", return_value=["RELIANCE", "NIFTY BANK"]), \
         patch("src.worker.main.get_settings", return_value=MagicMock()), \
         patch("src.worker.main.get_session_factory", return_value=MagicMock(side_effect=lambda: MagicMock())), \
         patch("src.worker.main.get_market_data_client", return_value=MagicMock()), \
         patch("src.worker.main.get_redis_cache", return_value=MagicMock()), \
         patch("src.worker.main.generate_recommendation", side_effect=_flaky_generate) as mock_generate:
        run_one_cycle()  # must not raise

    called_symbols = {c.kwargs["symbol"] for c in mock_generate.call_args_list}
    assert called_symbols == {"RELIANCE", "NIFTY BANK"}
