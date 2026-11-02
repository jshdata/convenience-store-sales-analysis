from datetime import datetime
from unittest.mock import Mock

import pytest

from cv_store.integrations.slack import home, home_data, web
from cv_store.integrations.slack.home_charts import ChartStore, render_chart
from cv_store.integrations.slack.home_data import HomeFilters, filters_from_view


@pytest.fixture
def home_rows():
    return [
        dict(sale_date=datetime(2024, 11, day), store_type=store, sum_amount=amount,
             store_count=10, sum_amount_growth=growth, avg_sum_amount_growth=1,
             growth_deviation=deviation)
        for day in (20, 21, 22)
        for store, amount, growth, deviation in (("CU", 100, 8, 1.252), ("GS25", 200, 3, -1.461), ("seven", 300, -2, 0))
    ]


def test_home_filters_use_view_state_and_validate_dates():
    view = {"private_metadata": HomeFilters().metadata(), "state": {"values": {
        "home_dates": {"home_start": {"selected_date": "2024-11-21"}, "home_end": {"selected_date": "2024-11-22"}},
        "home_options": {"home_store": {"selected_option": {"value": "CU"}}, "home_chart": {"selected_option": {"value": "brand"}}},
    }}}
    assert filters_from_view(view, True).__dict__ == HomeFilters("2024-11-21", "2024-11-22", "CU", "brand").__dict__
    view["state"]["values"]["home_dates"]["home_end"]["selected_date"] = "2024-11-20"
    with pytest.raises(ValueError):
        filters_from_view(view, True)
    assert filters_from_view({"private_metadata": "not json"}).__dict__ == HomeFilters().__dict__


def test_home_uses_existing_anomaly_boundaries_and_pairwise_data(monkeypatch, home_rows):
    monkeypatch.setattr(home_data.repository, "get_dashboard_sales", lambda: home_rows)
    context = Mock(return_value={"news": [], "videos": []})
    monkeypatch.setattr(home_data.repository, "get_dashboard_context", context)
    snapshot = home_data.load_snapshot(HomeFilters("2024-11-21", "2024-11-21", "CU"))
    assert snapshot["amount"] == 100
    assert snapshot["share"] == pytest.approx(100 / 6)
    assert snapshot["anomalies"][0]["kind"] == "high"
    assert [item["points"][0][1] for item in snapshot["series"]] == [5, 5, 10]
    context.assert_called_once_with("2024-11-21", "CU", limit=3)


def test_chart_store_expires_evicts_and_does_not_guess_tokens():
    clock = Mock(return_value=0)
    store = ChartStore(ttl=10, capacity=1, clock=clock)
    old = store.put(b"old")
    token = store.put(b"new")
    assert len(token) == 48 and token != old
    assert store.get(old) is None
    assert store.get("not-a-token") is None
    assert store.get(token) == b"new"
    clock.return_value = 11
    assert store.get(token) is None


def test_chart_url_only_returns_prepared_png(monkeypatch):
    monkeypatch.setattr(web, "validate_settings", lambda: (["missing"], []))
    store = ChartStore()
    monkeypatch.setattr(web, "chart_store", store)
    token = store.put(b"synthetic-png")
    client = web.create_app(start_socket=False).test_client()
    response = client.get(f"/slack/home-chart/{token}.png")
    assert response.status_code == 200 and response.data == b"synthetic-png"
    assert response.mimetype == "image/png"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert client.get("/slack/home-chart/not-found.png").status_code == 404


def test_home_action_acknowledges_before_query(monkeypatch):
    # Capture actual registered callback with a minimal registrar.
    callbacks = {}
    registrar = Mock()
    registrar.event.side_effect = lambda name: lambda handler: callbacks.setdefault(name, handler)
    registrar.action.side_effect = lambda name: lambda handler: callbacks.setdefault(name, handler)
    home.register_home_handlers(registrar)
    ack = Mock()
    update = Mock(side_effect=lambda *args: ack.assert_called_once())
    monkeypatch.setattr(home, "update_home", update)
    callbacks["home_refresh"](ack, {"user": {"id": "U_TEST"}, "view": {}}, Mock())
    update.assert_called_once()
    callbacks["app_home_opened"]({"tab": "messages", "user": "U_TEST"}, Mock())
    assert update.call_count == 1


def test_home_template_keeps_block_limits_and_metadata(monkeypatch, home_rows):
    monkeypatch.setenv("DASHBOARD_URL", "https://example.streamlit.app/")
    monkeypatch.setattr(home_data.repository, "get_dashboard_sales", lambda: home_rows)
    monkeypatch.setattr(home_data.repository, "get_dashboard_context", lambda *args, **kwargs: {"news": [], "videos": []})
    filters = HomeFilters("2024-11-20", "2024-11-22", "CU")
    snapshot = home_data.load_snapshot(filters)
    view = home.build_view(filters, snapshot, "https://example.test/synthetic.png")
    assert view["type"] == "home" and len(view["blocks"]) < 100
    assert filters_from_view(view).__dict__ == filters.__dict__
    assert sum(block["type"] == "image" for block in view["blocks"]) == 1
    assert "DB_PASSWORD" not in str(view)


def test_home_chart_is_png():
    pytest.importorskip("matplotlib")
    png = render_chart([dict(title="CU - GS25", limits={"low": -1, "high": 1},
                             points=[("2024-11-21", 2), ("2024-11-22", -2)])])
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert render_chart([]) is None
