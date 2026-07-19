"""Parser for the 'Revamped feedback' sheet.

Structure (verified directly against the live sheet):
  - Row 5 is the header; data starts row 6, one row per calendar date, running
    all the way to year-end (future dates are pre-filled with zeros - harmless,
    period filtering never selects them for a "current" period).
  - Columns 2-20 (Starmall..Website, 19 locations) are DAILY FEEDBACK RESPONSE
    COUNTS per location - this is the only per-location breakdown available.
  - 'Professionalism' and 'Overall' are DAILY AVERAGE SCORES (1-5 scale) but are
    sheet-wide aggregates, not broken out per location - there is no per-shop
    satisfaction score in this sheet, only per-shop response counts.
  - The sheet's own 'Total' and sparse weekly-total columns are not used - Total
    is recomputed from the 19 location columns for consistency with the rest of
    the app, and weekly/monthly rollups are computed by period filtering, not
    read from the sheet's own boundaries.
  - A separate "FEEDBACK TARGETS" table lives off to the right at AD4:AG26:
    header 'SHOP | Links Sent | Online | Walk-Ins' at row 6, one row per shop,
    a 'Totals' row closing it out. This is a single undated snapshot (no daily
    breakdown) that the user maintains manually - it's the 'sent' denominator
    needed to compute an actual online feedback response rate, which nothing
    else in this sheet provides.
"""
import threading
import time

import pandas as pd

from app.config import Config
from app.sheets_client import get_worksheet_values

_HEADER_ROW_INDEX = 4  # 0-indexed; row 5
_DATA_START_INDEX = 5  # 0-indexed; row 6
_DATE_COL = 1
_SHOP_COLS = slice(2, 21)  # Starmall .. Website
_PROFESSIONALISM_COL = 23
_OVERALL_COL = 24

_LINKS_SHOP_COL = 29  # column AD
_LINKS_SENT_COL = 30  # column AE
_LINKS_ONLINE_COL = 31  # column AF
_LINKS_WALKIN_COL = 32  # column AG

_lock = threading.Lock()
_cache = {"fetched_at": 0.0, "by_shop": None, "daily": None, "links": None}


def _to_float(v: str) -> float:
    v = v.strip()
    try:
        return float(v)
    except ValueError:
        return 0.0


def _parse_feedback(values: list):
    header = values[_HEADER_ROW_INDEX]
    shops = [h.strip() for h in header[_SHOP_COLS]]

    by_shop_records = []
    daily_records = []

    for row in values[_DATA_START_INDEX:]:
        date_str = row[_DATE_COL].strip() if len(row) > _DATE_COL else ""
        if not date_str:
            continue

        shop_counts = [int(_to_float(row[i])) if i < len(row) else 0 for i in range(2, 21)]
        total = sum(shop_counts)

        for shop, count in zip(shops, shop_counts):
            by_shop_records.append({"Date": date_str, "Shop": shop, "Responses": count})

        prof = _to_float(row[_PROFESSIONALISM_COL]) if len(row) > _PROFESSIONALISM_COL else 0.0
        overall = _to_float(row[_OVERALL_COL]) if len(row) > _OVERALL_COL else 0.0
        daily_records.append({"Date": date_str, "Responses": total, "Professionalism": prof, "Overall": overall})

    by_shop_df = pd.DataFrame(by_shop_records, columns=["Date", "Shop", "Responses"])
    daily_df = pd.DataFrame(daily_records, columns=["Date", "Responses", "Professionalism", "Overall"])

    for df in (by_shop_df, daily_df):
        if not df.empty:
            df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    by_shop_df = by_shop_df.dropna(subset=["Date"])
    daily_df = daily_df.dropna(subset=["Date"])

    return by_shop_df.reset_index(drop=True), daily_df.reset_index(drop=True)


def _parse_feedback_links(values: list) -> pd.DataFrame:
    header_idx = None
    for i, row in enumerate(values):
        if len(row) > _LINKS_SHOP_COL and row[_LINKS_SHOP_COL].strip().upper() == "SHOP":
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame(columns=["Shop", "Links Sent", "Online", "Walk-Ins"])

    records = []
    for row in values[header_idx + 1:]:
        shop = row[_LINKS_SHOP_COL].strip() if len(row) > _LINKS_SHOP_COL else ""
        if not shop or shop.upper() == "TOTALS":
            break
        sent = _to_float(row[_LINKS_SENT_COL]) if len(row) > _LINKS_SENT_COL else 0.0
        online = _to_float(row[_LINKS_ONLINE_COL]) if len(row) > _LINKS_ONLINE_COL else 0.0
        walkins = _to_float(row[_LINKS_WALKIN_COL]) if len(row) > _LINKS_WALKIN_COL else 0.0
        records.append({"Shop": shop, "Links Sent": sent, "Online": online, "Walk-Ins": walkins})

    return pd.DataFrame(records, columns=["Shop", "Links Sent", "Online", "Walk-Ins"])


def _load(force_refresh: bool):
    with _lock:
        if (
            not force_refresh
            and _cache["by_shop"] is not None
            and time.time() - _cache["fetched_at"] < Config.SHEET_CACHE_TTL_SECONDS
        ):
            return _cache["by_shop"], _cache["daily"], _cache["links"]

    values = get_worksheet_values(Config.SHEET_FEEDBACK, force_refresh=force_refresh)
    by_shop_df, daily_df = _parse_feedback(values)
    links_df = _parse_feedback_links(values)

    with _lock:
        _cache["by_shop"] = by_shop_df
        _cache["daily"] = daily_df
        _cache["links"] = links_df
        _cache["fetched_at"] = time.time()

    return by_shop_df, daily_df, links_df


def load_feedback_by_shop(force_refresh: bool = False) -> pd.DataFrame:
    by_shop, _, _ = _load(force_refresh)
    return by_shop


def load_feedback_daily(force_refresh: bool = False) -> pd.DataFrame:
    _, daily, _ = _load(force_refresh)
    return daily


def load_feedback_links(force_refresh: bool = False) -> pd.DataFrame:
    _, _, links = _load(force_refresh)
    return links
