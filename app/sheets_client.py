import json
import threading
import time

import gspread
from google.oauth2.service_account import Credentials

from app.config import Config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_lock = threading.Lock()
_client = None
_cache = {}  # sheet_name -> (fetched_at, values)


def _get_client():
    global _client
    if _client is not None:
        return _client

    if Config.GOOGLE_CREDENTIALS_JSON:
        info = json.loads(Config.GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif Config.GOOGLE_CREDENTIALS_FILE:
        creds = Credentials.from_service_account_file(
            Config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
    else:
        raise RuntimeError(
            "No Google credentials configured. Set GOOGLE_CREDENTIALS_JSON or "
            "GOOGLE_CREDENTIALS_FILE."
        )

    _client = gspread.authorize(creds)
    return _client


def get_worksheet_values(sheet_name: str, force_refresh: bool = False):
    """Returns all values (list of rows) for a worksheet, cached with a TTL."""
    with _lock:
        cached = _cache.get(sheet_name)
        if not force_refresh and cached is not None:
            fetched_at, values = cached
            if time.time() - fetched_at < Config.SHEET_CACHE_TTL_SECONDS:
                return values

    client = _get_client()
    sh = client.open_by_key(Config.SPREADSHEET_ID)
    ws = sh.worksheet(sheet_name)
    values = ws.get_all_values()

    with _lock:
        _cache[sheet_name] = (time.time(), values)

    return values


def clear_cache():
    with _lock:
        _cache.clear()
