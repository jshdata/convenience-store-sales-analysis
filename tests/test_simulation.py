from contextlib import contextmanager
from datetime import date, datetime
import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from cv_store.analysis.anomalies import ANOMALY_THRESHOLDS
from cv_store.simulation import home, service, store
from cv_store.integrations.slack.notifications import anomaly_payload


@pytest.fixture
def replay_rows():
    return [dict(sale_date=datetime(2024, 11, day), store_type=brand, sum_amount=1000,
                 growth_deviation=value if day == 21 else 0)
            for day in (20, 21, 22)
            for brand, value in (("CU", 1.252), ("GS25", -1.461), ("seven", 0))]


def test_preview_range_is_inclusive_and_never_creates_a_run(monkeypatch, replay_rows):
    monkeypatch.setattr(service.repository, "get_dashboard_sales", lambda: replay_rows)
    create = Mock()
    monkeypatch.setattr(service.store, "create_run", create)
    plan = service.preview("2024-11-20", "2024-11-22")
    assert plan["days"] == 3 and len(plan["events"]) == 2
    assert {e["kind"] for e in plan["events"]} == {"high", "low"}
    assert {e["day"] for e in plan["events"]} == {"2024-11-21"}
    assert len(service.preview("2024-11-21", "2024-11-21", "CU")["events"]) == 1
    create.assert_not_called()
    with pytest.raises(ValueError):
        service.preview("2024-11-22", "2024-11-20")
    with pytest.raises(ValueError, match="매출이 없습니다"):
        service.preview("2024-11-19", "2024-11-22")
    monkeypatch.setattr(service.repository, "get_dashboard_sales", lambda: replay_rows + [replay_rows[0]])
    with pytest.raises(ValueError, match="중복"):
        service.preview("2024-11-20", "2024-11-22")


@pytest.fixture
def run():
    return dict(id=str(uuid4()), owner_id="U_TEST", start_day="2024-11-20", end_day="2024-11-22",
                next_day="2024-11-21", last_day="2024-11-20", store_scope="ALL", channel_id="C_TEST",
                thresholds=ANOMALY_THRESHOLDS, status="ready", processed_days=1, sent_count=0, events=[])


def test_reservation_precedes_send_and_receipt_precedes_day_advance(monkeypatch, run, replay_rows):
    calls = Mock()
    monkeypatch.setattr(service.store, "claim_day", Mock(return_value=run))
    reserve = Mock(side_effect=[str(uuid4()), str(uuid4())])
    mark, finish = Mock(), Mock()
    client = Mock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "123.1"}
    for name, mock in (("reserve", reserve), ("post", client.chat_postMessage), ("mark", mark), ("finish", finish)):
        calls.attach_mock(mock, name)
    monkeypatch.setattr(service.store, "reserve_event", reserve)
    monkeypatch.setattr(service.store, "mark_sent", mark)
    monkeypatch.setattr(service.store, "finish_day", finish)
    monkeypatch.setattr(service.repository, "get_sales_for_date", lambda _: [r for r in replay_rows if r["sale_date"].day == 21])
    monkeypatch.setattr(service, "anomaly_payload", lambda row, day, kind, simulation_id: {"text": "synthetic"})
    monkeypatch.setattr(service.time, "sleep", lambda _: None)
    result = service.advance_day(client, "U_TEST", run["id"], "2024-11-21")
    assert result["sent"] == 2
    assert [c[0] for c in calls.mock_calls] == ["reserve", "post", "mark", "reserve", "post", "mark", "finish"]


def test_stale_or_concurrent_button_does_not_send(monkeypatch, run):
    monkeypatch.setattr(service.store, "claim_day", Mock(side_effect=store.StateChanged))
    client = Mock()
    with pytest.raises(store.StateChanged):
        service.advance_day(client, "U_TEST", run["id"], "2024-11-21")
    client.chat_postMessage.assert_not_called()


def test_uncertain_slack_request_stops_without_retry(monkeypatch, run, replay_rows):
    monkeypatch.setattr(service.store, "claim_day", Mock(return_value=run))
    event_id = str(uuid4())
    monkeypatch.setattr(service.store, "reserve_event", Mock(return_value=event_id))
    attention, finish = Mock(), Mock()
    monkeypatch.setattr(service.store, "mark_attention", attention)
    monkeypatch.setattr(service.store, "finish_day", finish)
    monkeypatch.setattr(service.repository, "get_sales_for_date", lambda _: [r for r in replay_rows if r["sale_date"].day == 21])
    monkeypatch.setattr(service, "anomaly_payload", lambda *args, **kwargs: {"text": "synthetic"})
    client = Mock()
    client.chat_postMessage.side_effect = TimeoutError("synthetic private detail")
    with pytest.raises(RuntimeError, match="자동 재발송하지 않습니다"):
        service.advance_day(client, "U_TEST", run["id"], "2024-11-21")
    client.chat_postMessage.assert_called_once()
    attention.assert_called_once_with(run["id"], event_id, note="publish_unknown")
    finish.assert_not_called()


def test_quiet_day_advances_without_posting(monkeypatch, run, replay_rows):
    monkeypatch.setattr(service.store, "claim_day", Mock(return_value=run))
    monkeypatch.setattr(service.repository, "get_sales_for_date", lambda _: [r for r in replay_rows if r["sale_date"].day == 20])
    finish = Mock()
    monkeypatch.setattr(service.store, "finish_day", finish)
    client = Mock()
    assert service.advance_day(client, "U_TEST", run["id"], "2024-11-20")["sent"] == 0
    client.chat_postMessage.assert_not_called()
    finish.assert_called_once_with("U_TEST", run["id"], "2024-11-20")


def test_claim_binds_owner_and_rejects_already_advanced_day(monkeypatch, run):
    cursor = Mock()
    cursor.fetchone.return_value = dict(run, start_day=date(2024, 11, 20), end_day=date(2024, 11, 22),
                                          next_day=date(2024, 11, 22), last_day=date(2024, 11, 21))
    @contextmanager
    def tx():
        yield cursor
    monkeypatch.setattr(store, "transaction", tx)
    with pytest.raises(store.StateChanged):
        store.claim_day("U_TEST", run["id"], "2024-11-21")
    sql, params = cursor.execute.call_args.args
    assert "owner_id = %s FOR UPDATE" in sql and params == (run["id"], "U_TEST")
    assert cursor.execute.call_count == 1


def test_simulation_payload_is_labeled_and_dashboard_stops_at_day(monkeypatch):
    monkeypatch.setenv("DASHBOARD_URL", "https://example.streamlit.app/")
    from cv_store.integrations.slack import notifications
    monkeypatch.setattr(notifications.repository, "get_ytb_links_by_date_and_store", lambda *args: [])
    monkeypatch.setattr(notifications.repository, "get_news_links_by_date_and_store", lambda *args: [])
    payload = anomaly_payload(dict(store_type="CU", sum_amount=1000, growth_deviation=1.3), "2024-11-21", "high", str(uuid4()))
    assert payload["text"].startswith("[시뮬레이션")
    url = payload["attachments"][-1]["actions"][0]["url"]
    assert "end=2024-11-21" in url and "as_of=2024-11-21" in url


def test_simulation_home_keeps_expected_day_in_button_and_hides_completed_step(run):
    values = dict(start="2024-11-20", end="2024-11-22", scope="ALL")
    view = home.build_view(values, run)
    button = next(e for b in view["blocks"] if b["type"] == "actions" for e in b["elements"] if e.get("action_id") == "simulation_next")
    assert json.loads(button["value"]) == {"run_id": run["id"], "day": "2024-11-21"}
    run["status"] = "completed"
    assert "simulation_next" not in str(home.build_view(values, run))
    assert len(view["blocks"]) < 100


def test_simulation_preview_action_acknowledges_and_never_posts(monkeypatch):
    callbacks = {}
    app = Mock()
    app.action.side_effect = lambda key: lambda handler: callbacks.setdefault(key, handler)
    home.register_handlers(app)
    ack, client = Mock(), Mock()
    preview = Mock(side_effect=lambda **kwargs: (ack.assert_called_once() or dict(events=[], days=3, **kwargs)))
    show = Mock()
    monkeypatch.setattr(home.service, "preview", preview)
    monkeypatch.setattr(home, "show", show)
    body = dict(user={"id": "U_TEST"}, view={}, actions=[{"action_id": "simulation_preview"}])
    callbacks["simulation_preview"](ack, body, client)
    preview.assert_called_once_with(start="2024-11-20", end="2024-11-22", scope="ALL")
    client.chat_postMessage.assert_not_called()
    show.assert_called_once()


def test_simulation_receipt_storage_failure_is_not_retried(monkeypatch, run, replay_rows):
    monkeypatch.setattr(service.store, "claim_day", Mock(return_value=run))
    event_id = str(uuid4())
    monkeypatch.setattr(service.store, "reserve_event", Mock(return_value=event_id))
    monkeypatch.setattr(service.store, "mark_sent", Mock(side_effect=RuntimeError("database unavailable")))
    attention = Mock()
    monkeypatch.setattr(service.store, "mark_attention", attention)
    monkeypatch.setattr(service.repository, "get_sales_for_date", lambda _: [r for r in replay_rows if r["sale_date"].day == 21])
    monkeypatch.setattr(service, "anomaly_payload", lambda *args, **kwargs: {"text": "synthetic"})
    client = Mock()
    client.chat_postMessage.return_value = {"ts": "123.1"}
    with pytest.raises(RuntimeError):
        service.advance_day(client, "U_TEST", run["id"], "2024-11-21")
    client.chat_postMessage.assert_called_once()
    attention.assert_called_once_with(run["id"], event_id, note="publish_unknown")
