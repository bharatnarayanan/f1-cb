"""canonical_logic -> Pine Script v5 export (F5.5).

Generated code, not executed anywhere in this codebase — the founder
reviews and pastes it into TradingView themselves. No live push exists or
is planned (docs/CLAUDE.md section 4: "Pine Script export for TradingView
(no live push — no such public API exists)").
"""

from typing import Any

_FIELD_NAMES = {"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}


def _pine_operand(operand: Any) -> str:
    if isinstance(operand, (int, float)):
        return str(operand)
    if "field" in operand:
        return _FIELD_NAMES[operand["field"]]
    if "indicator" in operand:
        name = operand["indicator"]
        period = operand["period"]
        params = operand.get("params", {})
        if name == "SMA":
            return f"ta.sma(close, {period})"
        if name == "EMA":
            return f"ta.ema(close, {period})"
        if name == "RSI":
            return f"ta.rsi(close, {period})"
        if name == "MACD":
            return f"ta.macd(close, {period}, {params.get('slowperiod', 26)}, {params.get('signalperiod', 9)})[0]"
        if name == "VWAP":
            return "ta.vwap(close)"
        if name == "SUPERTREND":
            return f"ta.supertrend({params.get('multiplier', 3)}, {period})[0]"
        raise ValueError(f"unsupported indicator for Pine export: {name!r}")
    raise ValueError(f"malformed operand: {operand!r}")


def _pine_condition(condition: dict) -> str:
    left = _pine_operand(condition["left"])
    right = _pine_operand(condition["right"])
    return f"({left} {condition['operator']} {right})"


def _pine_conditions(conditions: list[dict], logic: str) -> str:
    joiner = " and " if logic == "AND" else " or "
    return joiner.join(_pine_condition(c) for c in conditions)


def export_to_pine_script(canonical_logic: dict[str, Any], strategy_name: str) -> str:
    entry = canonical_logic["entry"]
    entry_expr = _pine_conditions(entry["conditions"], entry.get("logic", "AND"))

    guards = canonical_logic.get("guards", [])
    guard_expr = " and ".join(_pine_condition(g) for g in guards)
    full_entry_expr = f"{entry_expr} and {guard_expr}" if guard_expr else entry_expr

    stop_loss = canonical_logic["exit"]["stop_loss"]
    stop_lines = []
    if stop_loss.get("type") in ("below_ma", "below_vwap"):
        ref = _pine_operand(stop_loss.get("reference_indicator", {"indicator": "VWAP", "period": 1}))
        stop_lines.append(f"stopCondition = close < {ref}")
    elif stop_loss.get("type") in ("above_ma", "above_vwap"):
        ref = _pine_operand(stop_loss.get("reference_indicator", {"indicator": "VWAP", "period": 1}))
        stop_lines.append(f"stopCondition = close > {ref}")
    elif stop_loss.get("type") == "fixed_points":
        stop_lines.append(f"stopCondition = false  // fixed_points stop: {stop_loss.get('value')} pts, set via strategy.exit loss=")
    else:
        stop_lines.append("stopCondition = false")

    lines = [
        "//@version=5",
        f'strategy("{strategy_name}", overlay=true)',
        "",
        "// Generated from canonical_logic — review before using on TradingView.",
        "// No live push exists anywhere in this codebase; you paste this in yourself.",
        "",
        f"longCondition = {full_entry_expr}",
        *stop_lines,
        "",
        "if longCondition",
        '    strategy.entry("Long", strategy.long)',
        "",
        "if stopCondition",
        '    strategy.close("Long")',
    ]
    return "\n".join(lines)
