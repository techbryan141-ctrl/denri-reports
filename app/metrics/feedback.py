import pandas as pd

from app.metrics import formatting as fmt

_METRIC_SPECS = [
    ("Overall Experience", "Overall", "score"),
    ("Professionalism", "Professionalism", "score"),
    ("Feedback Responses", "Responses", "count"),
]

# Stated business rule (per user): online feedback requests should see a 75%
# response rate. There's no 'feedback sent' figure anywhere in the sheet yet
# (only responses received), so actual achievement can't be computed - this
# is a placeholder benchmark until that table exists.
TARGET_ONLINE_RESPONSE_RATE = 75.0


def _filter_daily(daily_df: pd.DataFrame, start, end) -> pd.DataFrame:
    if daily_df.empty:
        return daily_df
    dates = daily_df["Date"].dt.date
    return daily_df[(dates >= start) & (dates <= end)]


def _filter_by_shop(by_shop_df: pd.DataFrame, start, end) -> pd.DataFrame:
    if by_shop_df.empty:
        return by_shop_df
    dates = by_shop_df["Date"].dt.date
    return by_shop_df[(dates >= start) & (dates <= end)]


def compute_feedback_kpis(daily_period_df: pd.DataFrame) -> dict:
    responses = int(daily_period_df["Responses"].sum())
    if responses > 0:
        # Volume-weighted average, not a plain mean of daily averages - a day
        # with 50 responses should count for more than a day with 2.
        professionalism = float((daily_period_df["Professionalism"] * daily_period_df["Responses"]).sum() / responses)
        overall = float((daily_period_df["Overall"] * daily_period_df["Responses"]).sum() / responses)
    else:
        professionalism = 0.0
        overall = 0.0
    return {"Responses": responses, "Professionalism": professionalism, "Overall": overall}


def _score_status(score: float):
    if score >= 4.5:
        return "Excellent", "good"
    if score >= 4.0:
        return "Good", "good"
    if score >= 3.5:
        return "Fair", "warning"
    return "Needs Attention", "critical"


def _volume_status(pct_change):
    if pct_change is None:
        return "Stable", "neutral"
    if pct_change <= -15:
        return "Watch", "warning"
    if pct_change >= 15:
        return "Strong", "good"
    return "Stable", "neutral"


def build_comparison_rows(cur_kpis: dict, prev_kpis: dict) -> list:
    rows = []
    for label, key, kind in _METRIC_SPECS:
        current, previous = cur_kpis[key], prev_kpis[key]
        pc = fmt.pct_change(current, previous)
        dir_ = fmt.direction(current - previous)
        pc_str = f"{pc:+.1f}%" if pc is not None else "n/a"

        if kind == "score":
            status_label, status_tone = _score_status(current)
            value_fmt = lambda v: fmt.decimal(v, 2)
        else:
            status_label, status_tone = _volume_status(pc)
            value_fmt = fmt.count

        rows.append({
            "metric": label,
            "current": value_fmt(current),
            "previous": value_fmt(previous),
            "change": f"{fmt.glyph(dir_)} {pc_str}",
            "dir": dir_,
            "pct": pc_str,
            "status": status_label,
            "status_tone": status_tone,
        })
    return rows


def build_store_breakdown(cur_by_shop: pd.DataFrame, prev_by_shop: pd.DataFrame) -> list:
    shops = sorted(set(cur_by_shop["Shop"]) | set(prev_by_shop["Shop"]))
    rows = []

    for shop in shops:
        cur_val = int(cur_by_shop[cur_by_shop["Shop"] == shop]["Responses"].sum())
        prev_val = int(prev_by_shop[prev_by_shop["Shop"] == shop]["Responses"].sum())
        change, dir_ = fmt.combined_delta(cur_val, prev_val, places=0)
        rows.append({
            "shop": shop, "current": fmt.count(cur_val), "previous": fmt.count(prev_val),
            "change": change, "dir": dir_, "current_raw": cur_val,
        })

    rows.sort(key=lambda r: r["current_raw"], reverse=True)

    total_cur = int(cur_by_shop["Responses"].sum())
    total_prev = int(prev_by_shop["Responses"].sum())
    change, dir_ = fmt.combined_delta(total_cur, total_prev, places=0)
    rows.append({
        "shop": "TOTAL", "current": fmt.count(total_cur), "previous": fmt.count(total_prev),
        "change": change, "dir": dir_, "current_raw": total_cur,
    })

    return rows


def build_target_note(period_type: str):
    if period_type == "day":
        return None
    return {
        "target_pct": TARGET_ONLINE_RESPONSE_RATE,
        "note": (
            f"Target: receive back {TARGET_ONLINE_RESPONSE_RATE:.0f}% of feedback requests sent to online "
            "customers (walk-in feedback isn't held to this target). Actual achievement can't be computed "
            "yet - the sheet tracks responses received but not requests sent, so there's no denominator "
            "for a response rate. This will populate once a 'feedback sent' source is added."
        ),
    }


def build_summary(cur_kpis: dict, prev_kpis: dict, store_breakdown: list, period: dict) -> str:
    overall_diff = cur_kpis["Overall"] - prev_kpis["Overall"]
    overall_dir = fmt.direction(overall_diff)
    trend_word = {"up": "improved", "down": "declined", "neutral": "held steady"}[overall_dir]

    sentences = [
        f"Overall experience {trend_word} to {fmt.decimal(cur_kpis['Overall'], 2)}/5 vs {period['compared_to']}, "
        f"with professionalism at {fmt.decimal(cur_kpis['Professionalism'], 2)}/5 across "
        f"{fmt.count(cur_kpis['Responses'])} responses."
    ]

    shops = [r for r in store_breakdown if r["shop"] != "TOTAL"]
    if shops:
        top_shop = max(shops, key=lambda r: r["current_raw"])
        sentences.append(f"{top_shop['shop']} generated the most responses this period ({top_shop['current']}).")

    return " ".join(sentences)


def build_meeting_note(comparison_rows: list, period: dict) -> str:
    concerns = [r for r in comparison_rows if r["status_tone"] in ("warning", "critical")]
    if not concerns:
        return f"Feedback scores were healthy vs {period['compared_to']} - no escalations needed."

    parts = [f"{r['metric']} is at {r['status']} ({r['current']})" for r in concerns]
    return "Needs attention: " + "; ".join(parts) + "."


def build_section(daily_df: pd.DataFrame, by_shop_df: pd.DataFrame, period_type: str, period: dict) -> dict:
    cur_daily = _filter_daily(daily_df, period["start"], period["end"])
    prev_daily = _filter_daily(daily_df, period["prev_start"], period["prev_end"])
    cur_by_shop = _filter_by_shop(by_shop_df, period["start"], period["end"])
    prev_by_shop = _filter_by_shop(by_shop_df, period["prev_start"], period["prev_end"])

    cur_kpis = compute_feedback_kpis(cur_daily)
    prev_kpis = compute_feedback_kpis(prev_daily)

    comparison = build_comparison_rows(cur_kpis, prev_kpis)
    store_breakdown = build_store_breakdown(cur_by_shop, prev_by_shop)

    return {
        "summary": build_summary(cur_kpis, prev_kpis, store_breakdown, period),
        "comparison": comparison,
        "store_breakdown": store_breakdown,
        "target": build_target_note(period_type),
        "meeting_note": build_meeting_note(comparison, period),
    }
