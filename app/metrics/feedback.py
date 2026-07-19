import pandas as pd

from app.metrics import formatting as fmt

_METRIC_SPECS = [
    ("Overall Experience", "Overall", "score"),
    ("Professionalism", "Professionalism", "score"),
    ("Feedback Responses", "Responses", "count"),
]

# Stated business rule (per user): online feedback requests should see a 75%
# response rate. Walk-in feedback isn't held to this target. Sourced from the
# "FEEDBACK TARGETS" table at AD4:AG26 in Revamped feedback - a single
# undated snapshot the user maintains manually (not broken out by day), so it
# applies as-is to week/month views and isn't filtered by the selected period.
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


def _link_status(achv_pct):
    if achv_pct is None:
        return "No Data", "neutral"
    if achv_pct >= TARGET_ONLINE_RESPONSE_RATE:
        return "On Target", "good"
    if achv_pct >= 50:
        return "Below Target", "warning"
    return "Critical", "critical"


def build_feedback_links_rows(links_df: pd.DataFrame) -> list:
    rows = []
    for _, r in links_df.iterrows():
        sent, online, walkins = r["Links Sent"], r["Online"], r["Walk-Ins"]
        achv_pct = (online / sent * 100) if sent else None
        gap = (achv_pct - TARGET_ONLINE_RESPONSE_RATE) if achv_pct is not None else None
        status, tone = _link_status(achv_pct)

        rows.append({
            "shop": r["Shop"],
            "links_sent": fmt.count(sent),
            "online": fmt.count(online),
            "walkins": fmt.count(walkins),
            "achv_pct": fmt.pct(achv_pct) if achv_pct is not None else "n/a",
            "gap": fmt.pp(gap) if gap is not None else "n/a",
            "status": status,
            "status_tone": tone,
            "sent_raw": sent,
            "online_raw": online,
            "walkins_raw": walkins,
            "achv_pct_raw": achv_pct if achv_pct is not None else 0.0,
            "gap_raw": gap if gap is not None else 0.0,
        })

    rows.sort(key=lambda r: r["sent_raw"], reverse=True)

    total_sent, total_online, total_walkins = links_df["Links Sent"].sum(), links_df["Online"].sum(), links_df["Walk-Ins"].sum()
    total_achv = (total_online / total_sent * 100) if total_sent else None
    total_gap = (total_achv - TARGET_ONLINE_RESPONSE_RATE) if total_achv is not None else None
    status, tone = _link_status(total_achv)
    rows.append({
        "shop": "TOTAL",
        "links_sent": fmt.count(total_sent),
        "online": fmt.count(total_online),
        "walkins": fmt.count(total_walkins),
        "achv_pct": fmt.pct(total_achv) if total_achv is not None else "n/a",
        "gap": fmt.pp(total_gap) if total_gap is not None else "n/a",
        "status": status,
        "status_tone": tone,
        "sent_raw": total_sent,
        "online_raw": total_online,
        "walkins_raw": total_walkins,
        "achv_pct_raw": total_achv if total_achv is not None else 0.0,
        "gap_raw": total_gap if total_gap is not None else 0.0,
    })

    return rows


def build_target_summary(links_df: pd.DataFrame, period_type: str):
    if period_type == "day":
        return None

    total_sent = links_df["Links Sent"].sum() if not links_df.empty else 0
    if not total_sent:
        return {
            "target_pct": TARGET_ONLINE_RESPONSE_RATE,
            "achv_pct": None,
            "status": "No Data",
            "status_tone": "neutral",
            "note": "No feedback-link distribution data available yet.",
        }

    total_online = links_df["Online"].sum()
    total_walkins = links_df["Walk-Ins"].sum()
    achv_pct = total_online / total_sent * 100
    gap = achv_pct - TARGET_ONLINE_RESPONSE_RATE
    status, tone = _link_status(achv_pct)
    verb = "exceeding" if gap >= 0 else "missing"

    note = (
        f"Online feedback response rate is {fmt.pct(achv_pct)} against the {TARGET_ONLINE_RESPONSE_RATE:.0f}% "
        f"target ({fmt.count(total_online)} of {fmt.count(total_sent)} links sent) - {verb} it by {abs(gap):.1f} pp. "
        f"Walk-in feedback ({fmt.count(total_walkins)} responses) isn't held to this target."
    )

    return {
        "target_pct": TARGET_ONLINE_RESPONSE_RATE,
        "achv_pct": fmt.pct(achv_pct),
        "achv_pct_raw": achv_pct,
        "status": status,
        "status_tone": tone,
        "note": note,
    }


def build_summary(cur_kpis: dict, prev_kpis: dict, store_breakdown: list, target_summary, period: dict) -> str:
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

    if target_summary and target_summary.get("achv_pct") is not None:
        sentences.append(f"Online feedback links are converting at {target_summary['achv_pct']} against the {target_summary['target_pct']:.0f}% target.")

    return " ".join(sentences)


def build_meeting_note(comparison_rows: list, target_summary, period: dict) -> str:
    concerns = [r for r in comparison_rows if r["status_tone"] in ("warning", "critical")]
    parts = [f"{r['metric']} is at {r['status']} ({r['current']})" for r in concerns]

    if target_summary and target_summary["status_tone"] in ("warning", "critical"):
        parts.append(f"Online feedback response rate is {target_summary['status']} ({target_summary['achv_pct']} vs {target_summary['target_pct']:.0f}% target)")

    if not parts:
        return f"Feedback scores were healthy vs {period['compared_to']} - no escalations needed."

    return "Needs attention: " + "; ".join(parts) + "."


def build_section(
    daily_df: pd.DataFrame, by_shop_df: pd.DataFrame, links_df: pd.DataFrame, period_type: str, period: dict,
) -> dict:
    cur_daily = _filter_daily(daily_df, period["start"], period["end"])
    prev_daily = _filter_daily(daily_df, period["prev_start"], period["prev_end"])
    cur_by_shop = _filter_by_shop(by_shop_df, period["start"], period["end"])
    prev_by_shop = _filter_by_shop(by_shop_df, period["prev_start"], period["prev_end"])

    cur_kpis = compute_feedback_kpis(cur_daily)
    prev_kpis = compute_feedback_kpis(prev_daily)

    comparison = build_comparison_rows(cur_kpis, prev_kpis)
    store_breakdown = build_store_breakdown(cur_by_shop, prev_by_shop)
    target_summary = build_target_summary(links_df, period_type)
    feedback_links = build_feedback_links_rows(links_df) if target_summary else []

    return {
        "summary": build_summary(cur_kpis, prev_kpis, store_breakdown, target_summary, period),
        "comparison": comparison,
        "store_breakdown": store_breakdown,
        "target": target_summary,
        "feedback_links": feedback_links,
        "meeting_note": build_meeting_note(comparison, target_summary, period),
    }
