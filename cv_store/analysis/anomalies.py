"""기존 growth_deviation 임계값 판정. 값의 산출·통계 학습은 수행하지 않습니다."""

from cv_store.database.repository import normalize_store

ANOMALY_THRESHOLDS = {
    "CU": {"high": 1.252, "low": -1.344},
    "GS25": {"high": 1.135, "low": -1.461},
    "seven": {"high": 1.394, "low": -1.374},
}


def classify_anomaly(store, deviation):
    """임계값과 같아도 이상으로 판정합니다. 결측치는 판정하지 않습니다."""
    if deviation is None:
        return None
    thresholds = ANOMALY_THRESHOLDS[normalize_store(store)]
    if deviation >= thresholds["high"]:
        return "high"
    if deviation <= thresholds["low"]:
        return "low"
    return None
