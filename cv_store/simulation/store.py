"""PostgreSQL의 simulation 스키마에만 실행·발송 상태를 기록합니다."""

from contextlib import contextmanager
from datetime import date, timedelta
import json
from uuid import UUID, uuid4

from cv_store.config.settings import db_engine
from cv_store.database.connection import connection, dictionary_cursor


class StateChanged(Exception):
    """중복 클릭, 오래된 버튼 또는 이미 진행 중인 실행."""


@contextmanager
def transaction():
    if db_engine() != "postgresql":
        raise ValueError("Simulation state requires PostgreSQL")
    with connection() as conn:
        try:
            with dictionary_cursor(conn) as cursor:
                yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def run_key(value):
    return str(UUID(str(value)))


def _decode(row):
    if row:
        row["id"] = str(row["id"])
        for key in ("start_day", "end_day", "next_day", "last_day"):
            if row.get(key) is not None:
                row[key] = row[key].isoformat()
        if isinstance(row["thresholds"], str):
            row["thresholds"] = json.loads(row["thresholds"])
    return row


def create_run(owner, start, end, scope, channel, thresholds):
    with transaction() as cur:
        cur.execute(
            "INSERT INTO simulation.runs (id, owner_id, start_day, end_day, store_scope, channel_id, thresholds, next_day) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) RETURNING *",
            (str(uuid4()), owner, start, end, scope, channel, json.dumps(thresholds), start),
        )
        return _decode(cur.fetchone())


def get_run(owner, run_id=None):
    with transaction() as cur:
        # 재시작 등으로 중단된 작업은 확인 대상으로 남겨 자동 재발송하지 않습니다.
        cur.execute(
            "UPDATE simulation.runs SET status = 'attention', note = 'interrupted', updated_at = CURRENT_TIMESTAMP "
            "WHERE owner_id = %s AND status = 'processing' AND updated_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes'", (owner,),
        )
        if run_id:
            cur.execute("SELECT * FROM simulation.runs WHERE id = %s AND owner_id = %s", (run_key(run_id), owner))
        else:
            cur.execute("SELECT * FROM simulation.runs WHERE owner_id = %s ORDER BY created_at DESC LIMIT 1", (owner,))
        row = _decode(cur.fetchone())
        if not row:
            return None
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE status = 'sent') AS sent_count, "
            "COUNT(*) FILTER (WHERE status <> 'sent') AS unresolved_count FROM simulation.events WHERE run_id = %s", (row["id"],),
        )
        row.update(cur.fetchone())
        cur.execute("SELECT sale_day, store_type, kind, deviation, status FROM simulation.events "
                    "WHERE run_id = %s ORDER BY sale_day DESC, store_type LIMIT 10", (row["id"],))
        row["events"] = cur.fetchall()
        return row


def claim_day(owner, run_id, expected_day):
    expected_day = date.fromisoformat(expected_day).isoformat()
    with transaction() as cur:
        cur.execute("SELECT * FROM simulation.runs WHERE id = %s AND owner_id = %s FOR UPDATE", (run_key(run_id), owner))
        row = _decode(cur.fetchone())
        if not row or row["status"] != "ready" or row["next_day"] != expected_day:
            raise StateChanged()
        cur.execute("UPDATE simulation.runs SET status = 'processing', note = '', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (row["id"],))
        return row


def reserve_event(run_id, day, row, kind):
    event_id = str(uuid4())
    with transaction() as cur:
        cur.execute(
            "INSERT INTO simulation.events (id, run_id, sale_day, store_type, kind, amount, deviation, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 'sending') "
            "ON CONFLICT (run_id, sale_day, store_type) DO NOTHING RETURNING id",
            (event_id, run_key(run_id), day, row["store_type"], kind, int(row["sum_amount"]), float(row["growth_deviation"])),
        )
        if not cur.fetchone():
            raise StateChanged()
    return event_id


def mark_sent(event_id, slack_ts):
    with transaction() as cur:
        cur.execute("UPDATE simulation.events SET status = 'sent', slack_ts = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'sending' RETURNING id", (slack_ts, str(UUID(event_id))))
        if not cur.fetchone():
            raise StateChanged()


def mark_attention(run_id, event_id=None, note="publish_unknown"):
    with transaction() as cur:
        if event_id:
            cur.execute("UPDATE simulation.events SET status = 'unknown', updated_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'sending'", (str(UUID(event_id)),))
        cur.execute("UPDATE simulation.runs SET status = 'attention', note = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (note, run_key(run_id)))


def finish_day(owner, run_id, day):
    following = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    with transaction() as cur:
        cur.execute(
            "UPDATE simulation.runs SET last_day = %s, next_day = %s, processed_days = processed_days + 1, "
            "status = CASE WHEN end_day < %s::date THEN 'completed' ELSE 'ready' END, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = %s AND owner_id = %s AND status = 'processing' AND next_day = %s RETURNING id",
            (day, following, following, run_key(run_id), owner, day),
        )
        if not cur.fetchone():
            raise StateChanged()
