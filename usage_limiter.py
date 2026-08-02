"""
Daily usage counter — a lightweight safeguard so the public demo can't
silently run up API costs. Tracks how many gap analyses have been run
today using a JSON file on disk, and blocks further runs once a daily
cap is reached. This is a second layer of protection in addition to
the monthly spend limit set in the Anthropic Console (which is the
authoritative, billing-enforced limit).

Not designed for high-concurrency correctness (no file locking) —
it's a friendly soft cap for a conference demo, not a production
rate limiter.
"""

import json
import os
from datetime import date

COUNTER_FILE = os.path.join(os.path.dirname(__file__), "usage_counter.json")
DAILY_LIMIT = 20  # adjust as needed


def _load_counter() -> dict:
    if not os.path.exists(COUNTER_FILE):
        return {"date": str(date.today()), "count": 0}
    try:
        with open(COUNTER_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"date": str(date.today()), "count": 0}

    # Reset if it's a new day
    if data.get("date") != str(date.today()):
        return {"date": str(date.today()), "count": 0}

    return data


def _save_counter(data: dict) -> None:
    try:
        with open(COUNTER_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        pass  # fail silently — worst case, the cap doesn't persist across restarts


def get_usage_today() -> int:
    return _load_counter()["count"]


def get_daily_limit() -> int:
    return DAILY_LIMIT


def is_limit_reached() -> bool:
    return get_usage_today() >= DAILY_LIMIT


def increment_usage() -> int:
    """Records one analysis run. Returns the new count."""
    data = _load_counter()
    data["count"] += 1
    _save_counter(data)
    return data["count"]
