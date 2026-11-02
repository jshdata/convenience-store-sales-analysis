"""Slack 홈의 조회·집계. DB 쓰기와 메시지 발송은 수행하지 않습니다."""

from dataclasses import dataclass
from datetime import date, datetime
import json
import math

from cv_store.analysis.anomalies import ANOMALY_THRESHOLDS, classify_anomaly
from cv_store.database import repository

LABELS = {"CU": "CU", "GS25": "GS25", "seven": "세븐일레븐"}
PAIRS = (("CU", "GS25"), ("GS25", "seven"), ("CU", "seven"))


@dataclass(frozen=True)
class HomeFilters:
    start: str = "2024-11-01"
    end: str = "2024-12-31"
    store: str = "seven"
    chart: str = "pairs"

    def validated(self):
        start, end = repository.validate_date(self.start), repository.validate_date(self.end)
        if start > end:
            raise ValueError("Start date must not follow end date")
        if self.chart not in {"pairs", "brand"}:
            raise ValueError("Unknown chart")
        return HomeFilters(start, end, repository.normalize_store(self.store), self.chart)

    def metadata(self):
        return json.dumps(self.__dict__)


def filters_from_view(view, include_state=False):
    try:
        old = HomeFilters(**json.loads(view.get("private_metadata") or "{}")).validated()
    except (ValueError, TypeError):
        old = HomeFilters()
    if not include_state:
        return old
    values = view.get("state", {}).get("values", {})
    dates, options = values.get("home_dates", {}), values.get("home_options", {})
    return HomeFilters(
        dates.get("home_start", {}).get("selected_date") or old.start,
        dates.get("home_end", {}).get("selected_date") or old.end,
        (options.get("home_store", {}).get("selected_option") or {}).get("value") or old.store,
        (options.get("home_chart", {}).get("selected_option") or {}).get("value") or old.chart,
    ).validated()


def percentile(values, p):
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    lower = int(rank)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (rank - lower)


def _number(value):
    return None if value is None or not math.isfinite(float(value)) else float(value)


def load_snapshot(filters):
    filters = filters.validated()
    rows = []
    for original in repository.get_dashboard_sales():
        row = dict(original)
        value = row["sale_date"]
        row["day"] = value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
        row["store_type"] = repository.normalize_store(row["store_type"])
        row["growth_deviation"] = _number(row["growth_deviation"])
        row["sum_amount_growth"] = _number(row["sum_amount_growth"])
        rows.append(row)
    rows.sort(key=lambda row: (row["day"], row["store_type"]))
    if len({(row["day"], row["store_type"]) for row in rows}) != len(rows):
        raise ValueError("Duplicate daily data")
    period = [row for row in rows if filters.start <= row["day"] <= filters.end]
    focused = [row for row in period if row["store_type"] == filters.store]
    anomalies = [dict(row, kind=classify_anomaly(filters.store, row["growth_deviation"]))
                 for row in focused if classify_anomaly(filters.store, row["growth_deviation"]) is not None]
    total = sum(row["sum_amount"] for row in period)
    amount = sum(row["sum_amount"] for row in focused)
    series = []
    if filters.chart == "pairs":
        by_brand = {store: {r["day"]: r["sum_amount_growth"] for r in rows
                            if r["store_type"] == store and r["sum_amount_growth"] is not None} for store in LABELS}
        for first, second in PAIRS:
            differences = [(day, value - by_brand[second][day]) for day, value in by_brand[first].items()
                           if day in by_brand[second]]
            reference = [value for day, value in differences if day.startswith("2024-")]
            limits = {"low": percentile(reference, .05), "high": percentile(reference, .95)} if reference else None
            series.append(dict(title=f"{first} - {second.title() if second == 'seven' else second}", limits=limits,
                               points=[(day, value) for day, value in differences if filters.start <= day <= filters.end]))
    else:
        series.append(dict(title=f"{filters.store} vs three-brand average", limits=ANOMALY_THRESHOLDS[filters.store],
                           points=[(r["day"], r["growth_deviation"]) for r in focused if r["growth_deviation"] is not None]))
    latest_anomaly = anomalies[-1] if anomalies else None
    context_day = latest_anomaly["day"] if latest_anomaly else focused[-1]["day"] if focused else None
    context = repository.get_dashboard_context(context_day, filters.store, limit=3) if context_day else {"news": [], "videos": []}
    return dict(amount=amount, share=float(amount / total * 100) if total else 0,
                latest=focused[-1] if focused else None, anomalies=list(reversed(anomalies)), series=series,
                context_day=context_day, context=context, count=len(focused))
