import importlib
import json
import hashlib
import pkgutil
import socket
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

import cv_store
from cv_store.analysis.anomalies import classify_anomaly
from cv_store.config.settings import PROJECT_ROOT
from cv_store.database import repository
from cv_store.ingestion import sales, search_trends
from cv_store.integrations.slack import handlers, notifications


@pytest.mark.parametrize("store,value,result", [
    ("CU", 1.252, "high"), ("CU", -1.344, "low"),
    ("GS25", 1.135, "high"), ("GS25", -1.461, "low"),
    ("SEVEN", 1.394, "high"), ("Seven", -1.374, "low"),
    ("CU", 0, None), ("CU", None, None),
])
def test_original_anomaly_boundaries(store, value, result):
    assert classify_anomaly(store, value) == result


def test_all_original_data_and_state_bytes_preserved():
    manifest = json.loads((PROJECT_ROOT / "docs/file_manifest.json").read_text(encoding="utf-8"))
    preserved = [item for item in manifest if item.get("content_preserved")]
    assert len(preserved) == 20  # 13 local data/state + 7 unchanged web assets
    for item in preserved:
        path = PROJECT_ROOT / item["current"]
        # Datasets and checkpoints are local-only.
        if item["current"].startswith(("data/", "archive/simulation/state/")) and not path.exists():
            continue
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


@pytest.fixture
def sales_source(tmp_path):
    """공개 원본과 무관한 합성 데이터. 첫 행 누락 회귀 검증용."""
    import pandas as pd

    path = tmp_path / "synthetic_sales.xlsx"
    pd.DataFrame([
        [date(2024, 1, 1), 1000, 10, "CU"],
        [date(2024, 1, 2), 2000, 20, "SEVEN"],
    ]).to_excel(path, header=False, index=False)
    return path


def test_sales_headers_and_location_independent(monkeypatch, tmp_path, sales_source):
    monkeypatch.chdir(tmp_path)
    assert sales.DEFAULT_SOURCE.is_absolute()
    frame = sales.load_sales(sales_source)
    assert len(frame) == 2
    assert frame.iloc[0].sale_date == date(2024, 1, 1)
    assert frame.iloc[0].sale == 1000
    assert frame.iloc[0].store_count == 10
    assert frame.iloc[1].store_type == "seven"


def test_trend_first_row_is_data(tmp_path):
    source = tmp_path / "synthetic_trends.csv"
    source.write_text("2024-01-02,1.25,2.5,3.75,4\n2024-01-03,2,3,4,5\n", encoding="utf-8")
    frame = search_trends.load_search_trends(source)
    assert len(frame) == 2
    assert frame.iloc[0].DATE == date(2024, 1, 2)
    assert frame.iloc[0].seven == pytest.approx(1.25)


def test_imports_do_not_connect_or_start_browser(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External operation attempted during import")

    import pymysql
    from selenium import webdriver

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(pymysql, "connect", forbidden)
    monkeypatch.setattr(webdriver, "Chrome", forbidden)
    for item in pkgutil.walk_packages(cv_store.__path__, cv_store.__name__ + "."):
        module = importlib.import_module(item.name)
        importlib.reload(module)


def test_repository_binds_user_input(monkeypatch):
    fetch = Mock(return_value=[{"video_url": "example"}])
    monkeypatch.setattr(repository, "_fetch", fetch)
    assert repository.get_ytb_links_by_date_and_store("2024-10-02", "SEVEN") == ["example"]
    sql, params = fetch.call_args.args
    assert "%s" in sql and "2024-10-02" not in sql
    assert params == ("seven", "2024-10-02%")
    with pytest.raises(ValueError):
        repository.get_ytb_links_by_date_and_store("2024-02-30", "CU")


@pytest.fixture
def channels():
    return dict(CU="cu", GS25="gs", SEVEN="seven", YOUTUBE="yt", NEWS="news", ALERT="alert", TABLEAU="tableau")


def test_sales_mention_uses_channel_store(monkeypatch, channels):
    query = Mock(return_value=dict(sum_amount=1000, sum_amount_growth=1, avg_sum_amount_growth=2, growth_deviation=-1))
    monkeypatch.setattr(repository, "get_sales_data", query)
    say = Mock()
    handlers.handle_mention({"text": "<@U123> 2024-10-02", "channel": "cu"}, say, channels)
    query.assert_called_once_with("2024-10-02", "CU")
    assert "1,000원" in say.call_args.args[0]


def test_missing_brand_does_not_query(monkeypatch, channels):
    query = Mock()
    monkeypatch.setattr(repository, "get_news_links_by_date_and_store", query)
    say = Mock()
    handlers.handle_mention({"text": "2024-10-02", "channel": "news"}, say, channels)
    query.assert_not_called()
    assert "브랜드" in say.call_args.args[0]


def test_alerts_include_related_links_and_more_buttons(monkeypatch):
    monkeypatch.setattr(repository, "get_sales_for_date", lambda day: [
        dict(store_type="CU", sum_amount=1000, growth_deviation=1.252),
        dict(store_type="GS25", sum_amount=1000, growth_deviation=0),
    ])
    links = [f"https://example.test/{i}" for i in range(4)]
    monkeypatch.setattr(repository, "get_ytb_links_by_date_and_store", lambda *args: links)
    monkeypatch.setattr(repository, "get_news_links_by_date_and_store", lambda *args: links)
    client = Mock()
    assert notifications.send_anomaly_alerts(client, "alert", "2024-10-02") == 1
    payload = client.chat_postMessage.call_args.kwargs
    assert len(payload["attachments"]) == 2
    assert links[0] in payload["text"] and links[3] not in payload["text"]


def test_more_links_retains_original_message(monkeypatch):
    monkeypatch.setattr(repository, "get_news_links_by_date_and_store", lambda *args: ["a", "b", "c", "d"])
    ack, respond = Mock(), Mock()
    handlers.handle_more(ack, {"actions": [{"value": "2024-10-02|CU"}]}, respond, "news")
    ack.assert_called_once()
    assert respond.call_args.kwargs["text"] == "d"
    assert respond.call_args.kwargs["replace_original"] is False


def test_sales_existing_values_skip_and_conflicts_rollback(monkeypatch, sales_source):
    frame = sales.load_sales(sales_source).iloc[:1]
    row = frame.iloc[0]
    conn, cursor = Mock(), Mock()
    conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(sales, "connection", fake_connection)
    cursor.fetchall.return_value = [(row.sale_date, row.store_type, int(row.sale), int(row.store_count))]
    assert sales.insert_sales(frame) == 0
    cursor.executemany.assert_not_called()
    cursor.fetchall.return_value = [(row.sale_date, row.store_type, -1, int(row.store_count))]
    with pytest.raises(ValueError, match="입력 값이 다릅니다"):
        sales.insert_sales(frame)
    conn.rollback.assert_called_once()


def test_promotions_save_new_items_before_old_item(monkeypatch):
    from cv_store.collectors import promotions

    html = '''<div class="col-md-6"><small class="float-right text-white mr-3">2025-02-02</small>
    <strong>new</strong><i class="fa-coins"></i>1,000원</div>
    <div class="col-md-6"><small class="float-right text-white mr-3">2025-02-01</small>
    <strong>old</strong><i class="fa-coins"></i>1,000원</div>'''
    monkeypatch.setattr(promotions, "get_latest_update_date", lambda brand: "2025-02-01")
    monkeypatch.setattr(promotions.requests, "get", Mock(return_value=Mock(text=html)))
    conn, cursor = Mock(), Mock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(promotions, "connect_db", lambda: conn)
    promotions.run_crawling("CU")
    values = cursor.executemany.call_args.args[1]
    assert len(values) == 1 and values[0][2] == "new"
    conn.commit.assert_called_once()


def test_web_factory_does_not_require_db(monkeypatch):
    from cv_store.web.app import create_app

    monkeypatch.delenv("DB_HOST", raising=False)
    app = create_app()
    assert app.test_client().get("/test-db").status_code == 404
    assert app.debug is False
