"""로컬 .env와 Community Cloud DB 전용 Secrets 지원."""

from datetime import date, timedelta
import os

from cv_store.database.repository import normalize_store

DB_SECRET_KEYS = ("DB_ENGINE", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
                  "DB_SSLMODE", "DB_SSLROOTCERT", "DB_SSLROOTCERT_PEM")


def load_dashboard_secrets(secrets):
    try:
        values = {key: secrets[key] for key in DB_SECRET_KEYS if key in secrets}
    except FileNotFoundError:
        return
    for key, value in values.items():
        os.environ.setdefault(key, str(value))


def initial_filters(first, last, query):
    start, end = max(first, date(2024, 11, 1)), min(last, date(2024, 12, 31))
    if start > end:
        start, end = max(first, last - timedelta(days=60)), last
    brand, event = "seven", None
    try:
        candidate_start = date.fromisoformat(query.get("start", start.isoformat()))
        candidate_end = date.fromisoformat(query.get("end", end.isoformat()))
        if candidate_start <= candidate_end and candidate_end >= first and candidate_start <= last:
            start, end = max(first, candidate_start), min(last, candidate_end)
    except (ValueError, TypeError):
        pass
    try:
        brand = normalize_store(query.get("brand", "seven"))
    except ValueError:
        pass
    try:
        event = date.fromisoformat(query.get("event", "")).isoformat()
    except (ValueError, TypeError):
        pass
    return (start, end), brand, event


def simulation_cutoff(query):
    try:
        return date.fromisoformat(query.get("as_of", ""))
    except (ValueError, TypeError):
        return None
