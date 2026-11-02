"""대시보드 집계와 기존 이상치 판정의 연결."""

from urllib.parse import urlsplit

import pandas as pd

from cv_store.analysis.anomalies import classify_anomaly
from cv_store.database.repository import normalize_store

BRANDS = ("CU", "GS25", "seven")
LABELS = {"CU": "CU", "GS25": "GS25", "seven": "세븐일레븐"}
STATUS = {"high": "급등", "low": "급감", "normal": "정상", "missing": "미산출"}
PAIRS = (("CU", "GS25"), ("GS25", "seven"), ("CU", "seven"))


def sales_frame(rows):
    columns = ["sale_date", "store_type", "sum_amount", "store_count",
               "sum_amount_growth", "avg_sum_amount_growth", "growth_deviation"]
    frame = pd.DataFrame(rows, columns=columns)
    frame["sale_date"] = pd.to_datetime(frame["sale_date"])
    frame["store_type"] = frame["store_type"].map(normalize_store)
    for column in columns[2:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.duplicated(["sale_date", "store_type"]).any():
        raise ValueError("브랜드·날짜별 중복 매출이 있습니다.")
    frame["kind"] = [
        "missing" if pd.isna(value) else classify_anomaly(store, value) or "normal"
        for store, value in zip(frame["store_type"], frame["growth_deviation"])
    ]
    frame["brand"] = frame["store_type"].map(LABELS)
    frame["status"] = frame["kind"].map(STATUS)
    return frame.sort_values(["sale_date", "store_type"]).reset_index(drop=True)


def period_frame(frame, start, end):
    return frame.loc[frame["sale_date"].dt.date.between(start, end)].copy()


def sales_shares(frame):
    """조회한 카드 데이터의 3사 내 매출 비중. 전체 시장점유율이 아닙니다."""
    totals = frame.groupby("store_type")["sum_amount"].sum().reindex(BRANDS, fill_value=0)
    total = totals.sum()
    return totals / total * 100 if total else totals.astype(float) * 0


def pairwise_growth(frame, first, second):
    """같은 날짜의 두 브랜드 증감률 차이. 누락된 값은 0으로 대체하지 않습니다."""
    first, second = normalize_store(first), normalize_store(second)
    growth = frame.pivot(index="sale_date", columns="store_type", values="sum_amount_growth")
    growth = growth.reindex(columns=[first, second]).dropna()
    result = growth.rename(columns={first: "first_growth", second: "second_growth"}).reset_index()
    result["difference"] = result["first_growth"] - result["second_growth"]
    return result


def pairwise_thresholds(frame, first, second):
    """쌍별 차이의 2024년 고정 5·95백분위. 기존 Slack 임계값과 별개입니다."""
    reference = frame.loc[frame["sale_date"].dt.year == 2024]
    values = pairwise_growth(reference, first, second)["difference"]
    if values.empty:
        return None
    return {"low": float(values.quantile(.05)), "high": float(values.quantile(.95))}


def safe_link(value):
    """DB에 저장된 링크는 HTTP(S) 주소만 화면에 전달합니다."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username else None
    except ValueError:
        return None
