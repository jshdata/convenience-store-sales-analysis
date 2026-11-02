"""공유 대시보드 URL 구성. 토큰이나 DB 설정을 URL에 포함하지 않습니다."""

from datetime import date, timedelta
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cv_store.database.repository import normalize_store, validate_date


def dashboard_url(day=None, store=None):
    base = os.environ.get("DASHBOARD_URL", "").strip()
    if not base:
        return None
    try:
        parts = urlsplit(base)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            return None
        query = dict(parse_qsl(parts.query))
        if store:
            query["brand"] = normalize_store(store)
        if day:
            event = date.fromisoformat(validate_date(day))
            query.update(event=event.isoformat(), start=(event - timedelta(days=14)).isoformat(),
                         end=(event + timedelta(days=14)).isoformat())
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    except ValueError:
        return None
