from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from app.data.feedback import load_feedback_by_shop, load_feedback_daily
from app.data.footfall import get_footfall_gaps, load_footfall_df
from app.data.shops import load_shops_df
from app.metrics.executive_summary import build_report
from app.sheets_client import clear_cache

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@bp.route("/api/report")
def api_report():
    period_type = request.args.get("period", "week")
    if period_type not in ("day", "week", "month"):
        return jsonify({"error": "period must be one of day, week, month"}), 400

    date_str = request.args.get("date")
    ref_date = None
    if date_str:
        try:
            ref_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400

    df = load_shops_df()
    footfall_df = load_footfall_df()
    footfall_gaps = get_footfall_gaps()
    feedback_daily_df = load_feedback_daily()
    feedback_by_shop_df = load_feedback_by_shop()
    report = build_report(
        df, period_type, ref_date, footfall_df, footfall_gaps,
        feedback_daily_df, feedback_by_shop_df,
    )
    return jsonify(report)


@bp.route("/api/refresh", methods=["GET", "POST"])
def api_refresh():
    clear_cache()
    load_shops_df(force_refresh=True)
    load_footfall_df(force_refresh=True)
    load_feedback_daily(force_refresh=True)
    return jsonify({"status": "refreshed"})
