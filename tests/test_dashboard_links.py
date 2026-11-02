from datetime import date
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

from cv_store.dashboard.settings import initial_filters, load_dashboard_secrets
from cv_store.integrations.slack.dashboard import dashboard_url
from cv_store.integrations.slack import handlers, notifications


def test_alert_link_opens_requested_event_and_clamps_dates(monkeypatch):
    monkeypatch.setenv("DASHBOARD_URL", "https://example.streamlit.app/")
    url = dashboard_url("2024-11-21", "CU")
    params = {key: value[-1] for key, value in parse_qs(urlsplit(url).query).items()}
    dates, brand, event = initial_filters(date(2024, 11, 10), date(2024, 11, 30), params)
    assert dates == (date(2024, 11, 10), date(2024, 11, 30))
    assert brand == "CU" and event == "2024-11-21"
    assert "TOKEN" not in url and "PASSWORD" not in url


def test_invalid_filters_fall_back_and_local_url_is_not_shared(monkeypatch):
    dates, brand, event = initial_filters(date(2024, 1, 1), date(2025, 2, 6),
                                         {"start": "invalid", "brand": "other", "event": "bad"})
    assert dates == (date(2024, 11, 1), date(2024, 12, 31))
    assert brand == "seven" and event is None
    monkeypatch.setenv("DASHBOARD_URL", "http://127.0.0.1:8501")
    assert dashboard_url() is None


def test_dashboard_secret_allowlist_and_environment_precedence(monkeypatch):
    monkeypatch.setenv("DB_HOST", "existing.example.test")
    monkeypatch.delenv("DB_SSLROOTCERT_PEM", raising=False)
    monkeypatch.delenv("UNRELATED_DASHBOARD_SECRET", raising=False)
    load_dashboard_secrets({"DB_HOST": "other.example.test", "DB_SSLROOTCERT_PEM": "synthetic-ca",
                           "UNRELATED_DASHBOARD_SECRET": "not-copied"})
    import os
    assert os.environ["DB_HOST"] == "existing.example.test"
    assert os.environ["DB_SSLROOTCERT_PEM"] == "synthetic-ca"
    assert "UNRELATED_DASHBOARD_SECRET" not in os.environ


def test_dashboard_mention_and_alert_url_button(monkeypatch):
    monkeypatch.setenv("DASHBOARD_URL", "https://example.streamlit.app/")
    channels = dict(CU="cu", GS25="gs", SEVEN="seven", YOUTUBE="yt", NEWS="news", ALERT="alert", TABLEAU="tableau")
    say = Mock()
    handlers.handle_mention({"text": "<@U123> 대시보드", "channel": "cu"}, say, channels)
    assert "brand=CU" in say.call_args.args[0]
    monkeypatch.setattr(notifications.repository, "get_sales_for_date", lambda _: [
        dict(store_type="CU", sum_amount=1000, growth_deviation=1.252),
    ])
    monkeypatch.setattr(notifications.repository, "get_ytb_links_by_date_and_store", lambda *args: [])
    monkeypatch.setattr(notifications.repository, "get_news_links_by_date_and_store", lambda *args: [])
    client = Mock()
    assert notifications.send_anomaly_alerts(client, "alert", "2024-11-21") == 1
    url = client.chat_postMessage.call_args.kwargs["attachments"][-1]["actions"][0]["url"]
    assert "event=2024-11-21" in url and "brand=CU" in url
