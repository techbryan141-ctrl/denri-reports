"""Shared number/delta formatting for the report JSON payload.

The frontend renders arrows/colors from the `dir` field returned here — nothing
about a specific week's numbers is ever hardcoded, only the sign of the change.
"""

GLYPHS = {"up": "▲", "down": "▼", "neutral": "→"}


def money(value: float) -> str:
    return f"KES {value:,.2f}"


def count(value: float) -> str:
    return f"{value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def pp(value: float) -> str:
    return f"{value:+.1f} pp"


def decimal(value: float, places: int = 1) -> str:
    return f"{value:.{places}f}"


def direction(delta: float, epsilon: float = 0.05) -> str:
    if delta is None:
        return "neutral"
    if delta > epsilon:
        return "up"
    if delta < -epsilon:
        return "down"
    return "neutral"


def glyph(dir_: str) -> str:
    return GLYPHS.get(dir_, GLYPHS["neutral"])


def pct_change(current: float, previous: float):
    """Percent change; None when the previous value can't support a ratio."""
    if not previous:
        return None
    return (current - previous) / previous * 100


def combined_delta(current: float, previous: float, places: int = 0):
    """'<glyph> <signed diff> (<signed %>)' — the absolute-diff-plus-percentage
    style used by comparison tables (e.g. '▼ -284 (-10.0%)'). Returns
    (formatted_string, direction)."""
    diff = current - previous
    dir_ = direction(diff)
    pc = pct_change(current, previous)
    pc_str = f" ({pc:+.1f}%)" if pc is not None else ""
    return f"{glyph(dir_)} {diff:+,.{places}f}{pc_str}", dir_


def pp_delta(current: float, previous: float):
    """'<glyph> <signed pp>' for percentage-point deltas. Returns (string, direction)."""
    diff = current - previous
    dir_ = direction(diff)
    return f"{glyph(dir_)} {diff:+.1f} pp", dir_


def combined_money_delta(current: float, previous: float, places: int = 2):
    """Like combined_delta, but for a money-valued metric - carries a currency
    prefix on the diff (e.g. '▼ -KES 1,097,710.77 (-13.0%)') since a bare number
    would misread as a count."""
    diff = current - previous
    dir_ = direction(diff)
    pc = pct_change(current, previous)
    pc_str = f" ({pc:+.1f}%)" if pc is not None else ""
    sign = "+" if diff >= 0 else "-"
    return f"{glyph(dir_)} {sign}KES {abs(diff):,.{places}f}{pc_str}", dir_
