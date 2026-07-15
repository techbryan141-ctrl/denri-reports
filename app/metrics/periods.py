"""Period resolution: turns a period_type + optional anchor date into concrete
current/previous date windows. Weeks run Sunday-Saturday (verified against the
sheet's own week boundaries - see plan notes). Months are calendar months.

When no explicit ref_date is supplied, the period defaults to the one containing
the latest date actually present in the data (not the system clock, which may be
ahead of it) - i.e. the current, possibly still in-progress, day/week/month. The
filter bar's back/forward arrows are how you reach the prior completed period.
"""
import calendar
from datetime import date, timedelta


def _week_start(d: date) -> date:
    # Python's date.weekday(): Monday=0 ... Sunday=6
    days_since_sunday = (d.weekday() + 1) % 7
    return d - timedelta(days=days_since_sunday)


def _month_end(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def _fmt_range(start: date, end: date) -> str:
    if start == end:
        return start.strftime("%d %b %Y")
    if start.year == end.year:
        return f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"
    return f"{start.strftime('%d %b %Y')} - {end.strftime('%d %b %Y')}"


def _label(period_type: str, start: date, end: date) -> str:
    if period_type == "day":
        return start.strftime("%A, %d %B %Y")
    if period_type == "week":
        return f"Week of {start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"
    return start.strftime("%B %Y")


def _prev_window(period_type: str, start: date, end: date):
    """The window immediately preceding (start, end) for the given period_type."""
    if period_type == "day":
        return start - timedelta(days=1), start - timedelta(days=1)
    if period_type == "week":
        return start - timedelta(days=7), end - timedelta(days=7)
    if period_type == "month":
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        return prev_start, prev_end
    raise ValueError(f"Unknown period_type: {period_type!r} (expected day/week/month)")


def resolve_period(period_type: str, max_date: date, ref_date: date = None) -> dict:
    anchor = ref_date or max_date

    if period_type == "day":
        start = end = anchor

    elif period_type == "week":
        start = _week_start(anchor)
        end = start + timedelta(days=6)

    elif period_type == "month":
        start = anchor.replace(day=1)
        end = _month_end(start)

    else:
        raise ValueError(f"Unknown period_type: {period_type!r} (expected day/week/month)")

    prev_start, prev_end = _prev_window(period_type, start, end)
    days = (end - start).days + 1

    # Like-for-like comparison: if the current period is still in progress (it
    # extends past the latest data we actually have), comparing it against a
    # FULL prior period always makes it look like a crash - a week that's 3
    # days old isn't comparable to a complete 7-day prior week. Clip the prior
    # window to the same number of elapsed days instead.
    if end > max_date:
        elapsed_end = max_date if max_date >= start else start - timedelta(days=1)
        elapsed_days = (elapsed_end - start).days + 1
        if elapsed_days > 0:
            prev_end = prev_start + timedelta(days=elapsed_days - 1)
        else:
            prev_end = prev_start - timedelta(days=1)

    return {
        "period_type": period_type,
        "start": start,
        "end": end,
        "prev_start": prev_start,
        "prev_end": prev_end,
        "days": days,
        "label": _label(period_type, start, end),
        "date_range": _fmt_range(start, end),
        "compared_to": _fmt_range(prev_start, prev_end),
    }


def sequence_periods(period_type: str, start: date, end: date, count: int) -> list:
    """`count` consecutive (start, end, label) windows of period_type ending with
    the given period, oldest first - the backbone of the Revenue Bridge trend."""
    windows = [(start, end)]
    cur_start, cur_end = start, end
    for _ in range(count - 1):
        cur_start, cur_end = _prev_window(period_type, cur_start, cur_end)
        windows.append((cur_start, cur_end))
    windows.reverse()
    return [
        {"start": s, "end": e, "label": _label(period_type, s, e), "date_range": _fmt_range(s, e)}
        for s, e in windows
    ]
