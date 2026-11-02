"""2024년 전체 편차의 5·95백분위수에 대응하는 고정 임계값 판정.

기존 코드의 값은 재계산한 백분위수를 소수 셋째 자리로 반올림한 값과
6개 모두 일치합니다. 실행 중 재학습하지 않으며 근거는 docs/anomaly_method.md 참고.
"""

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
