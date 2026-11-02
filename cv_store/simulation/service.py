"""시작·종료일 미리보기와 하루 단위 알림 재생."""

from datetime import date, datetime, timedelta
import logging
import os
import time

from cv_store.analysis.anomalies import ANOMALY_THRESHOLDS
from cv_store.config.settings import load_local_env
from cv_store.database import repository
from cv_store.integrations.slack.notifications import anomaly_payload
from cv_store.simulation import store

logger = logging.getLogger(__name__)


class InputError(ValueError):
    """사용자에게 표시해도 되는 입력 검증 오류."""


def scope_stores(scope):
    try:
        return tuple(ANOMALY_THRESHOLDS) if scope == "ALL" else (repository.normalize_store(scope),)
    except ValueError:
        raise InputError("대상 브랜드를 확인해주세요.") from None


def classify(row, thresholds):
    value = row["growth_deviation"]
    if value is None:
        return None
    limits = thresholds[repository.normalize_store(row["store_type"])]
    return "high" if value >= limits["high"] else "low" if value <= limits["low"] else None


def _day(value):
    return value.date() if isinstance(value, datetime) else value


def validate_period(start, end):
    try:
        start, end = date.fromisoformat(repository.validate_date(start)), date.fromisoformat(repository.validate_date(end))
    except ValueError:
        raise InputError("날짜를 YYYY-MM-DD 형식으로 지정해주세요.") from None
    if start > end or (end - start).days > 730:
        raise InputError("시작일·종료일과 기간(최대 731일)을 확인해주세요.")
    return start, end


def preview(start, end, scope="ALL"):
    start, end = validate_period(start, end)
    brands = scope_stores(scope)
    rows = [dict(r, store_type=repository.normalize_store(r["store_type"])) for r in repository.get_dashboard_sales()]
    indexed = {(_day(r["sale_date"]), r["store_type"]): r for r in rows}
    if len(indexed) != len(rows):
        raise InputError("브랜드·날짜별 매출 중복을 확인해주세요.")
    events = []
    day = start
    while day <= end:
        for brand in brands:
            row = indexed.get((day, brand))
            if row is None:
                raise InputError(f"{day} {brand} 매출이 없습니다. 보유 기간 안으로 지정해주세요.")
            kind = classify(row, ANOMALY_THRESHOLDS)
            if kind:
                events.append(dict(day=day.isoformat(), store_type=brand, kind=kind,
                                   amount=int(row["sum_amount"]), deviation=float(row["growth_deviation"])))
        day += timedelta(days=1)
    return dict(start=start.isoformat(), end=end.isoformat(), scope=scope if scope == "ALL" else brands[0],
                days=(end - start).days + 1, events=events)


def create_run(owner, start, end, scope="ALL"):
    plan = preview(start, end, scope)
    load_local_env()
    channel = (os.environ.get("SLACK_CHANNEL_SIMULATION") or os.environ.get("SLACK_CHANNEL_ALERT") or "").strip()
    if not channel:
        raise InputError("시뮬레이션 알림 채널을 설정해주세요.")
    return store.create_run(owner, plan["start"], plan["end"], plan["scope"], channel, ANOMALY_THRESHOLDS)


def advance_day(client, owner, run_id, expected_day):
    run = store.claim_day(owner, run_id, expected_day)
    event_id = None
    try:
        brands = scope_stores(run["store_scope"])
        rows = [dict(row, store_type=repository.normalize_store(row["store_type"]))
                for row in repository.get_sales_for_date(expected_day)]
        selected = [row for row in rows if row["store_type"] in brands]
        if len(selected) != len(brands) or {r["store_type"] for r in selected} != set(brands):
            raise ValueError("Incomplete daily data")
        # 메시지는 전송 예약 전에 준비하여 조회 오류가 발송 불명 상태를 만들지 않게 합니다.
        candidates = []
        for row in selected:
            kind = classify(row, run["thresholds"])
            if kind:
                payload = anomaly_payload(row, expected_day, kind, simulation_id=run["id"])
                candidates.append((row, kind, payload))
        sent = 0
        for index, (row, kind, payload) in enumerate(candidates):
            if index:
                time.sleep(1.1)  # 같은 채널에 연속 전송하는 간격을 확보합니다.
            event_id = store.reserve_event(run["id"], expected_day, row, kind)
            response = client.chat_postMessage(channel=run["channel_id"], **payload)
            if not response.get("ts"):
                raise ValueError("Uncertain Slack response")
            store.mark_sent(event_id, response["ts"])
            event_id = None
            sent += 1
        store.finish_day(owner, run["id"], expected_day)
        return dict(day=expected_day, sent=sent)
    except Exception as exc:
        # 서버나 네트워크 중단 후 성공 여부가 불명확한 요청은 자동 재시도하지 않습니다.
        try:
            store.mark_attention(run["id"], event_id, note="publish_unknown" if event_id else "step_interrupted")
        except Exception:
            pass  # processing 상태는 5분 후 확인 대상으로 전환됩니다.
        logger.error("Simulation step stopped (%s)", type(exc).__name__)
        raise RuntimeError("처리가 중단되어 발송 상태 확인이 필요합니다. 자동 재발송하지 않습니다.") from None
