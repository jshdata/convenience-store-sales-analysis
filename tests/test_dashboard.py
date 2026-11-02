from datetime import date, datetime
from unittest.mock import Mock

import pytest

from cv_store.dashboard.model import pairwise_growth, pairwise_thresholds, period_frame, safe_link, sales_frame, sales_shares
from cv_store.database import repository


@pytest.fixture
def dashboard_rows():
    return [
        dict(sale_date=datetime(2024, 11, day), store_type=brand, sum_amount=sales,
             store_count=10, sum_amount_growth=2, avg_sum_amount_growth=1,
             growth_deviation=deviation if day == 21 else 0)
        for day in (20, 21, 22)
        for brand, sales, deviation in (("CU", 100, 1.252), ("GS25", 200, -1.461), ("seven", 300, 0))
    ]


def test_dashboard_uses_slack_boundaries_and_full_denominator(dashboard_rows):
    frame = sales_frame(dashboard_rows)
    period = period_frame(frame, date(2024, 11, 21), date(2024, 11, 21))
    assert dict(zip(period.store_type, period.kind)) == {"CU": "high", "GS25": "low", "seven": "normal"}
    assert sales_shares(period)["seven"] == 50
    assert sales_shares(period).sum() == pytest.approx(100)
    with pytest.raises(ValueError, match="중복"):
        sales_frame(dashboard_rows + [dashboard_rows[0]])


def test_missing_deviation_is_not_normal(dashboard_rows):
    dashboard_rows[0]["growth_deviation"] = None
    assert sales_frame(dashboard_rows).iloc[0]["kind"] == "missing"


def test_pairwise_growth_direction_and_missing_dates(dashboard_rows):
    for row in dashboard_rows:
        row["sum_amount_growth"] = {"CU": 8, "GS25": 3, "seven": -2}[row["store_type"]]
    frame = sales_frame(dashboard_rows)
    assert pairwise_growth(frame, "CU", "GS25")["difference"].tolist() == [5, 5, 5]
    assert pairwise_growth(frame, "GS25", "SEVEN")["difference"].tolist() == [5, 5, 5]
    assert pairwise_growth(frame, "CU", "SEVEN")["difference"].tolist() == [10, 10, 10]
    missing = frame[~((frame["store_type"] == "GS25") & (frame["sale_date"].dt.day == 21))]
    assert len(pairwise_growth(missing, "CU", "GS25")) == 2


def test_pairwise_lines_use_full_2024_reference(dashboard_rows):
    pytest.importorskip("plotly")
    from cv_store.dashboard.charts import pairwise_chart

    for row in dashboard_rows:
        row["sum_amount_growth"] = row["sale_date"].day - 20 if row["store_type"] == "CU" else 0
    # A later-year extreme must not affect the 2024 reference.
    later = [dict(row, sale_date=datetime(2025, 1, 1), sum_amount_growth=100 if row["store_type"] == "CU" else 0)
             for row in dashboard_rows[:3]]
    frame = sales_frame(dashboard_rows + later)
    bounds = pairwise_thresholds(frame, "CU", "GS25")
    assert bounds == pytest.approx({"low": .1, "high": 1.9})
    visible = period_frame(frame, date(2024, 11, 22), date(2024, 11, 22))
    fig = pairwise_chart(visible, "CU", "GS25", 3, bounds)
    assert [shape.y0 for shape in fig.layout.shapes] == pytest.approx([0, 1.9, .1])
    assert all(shape.line.dash == "solid" for shape in fig.layout.shapes[1:])
    assert fig.data[0].marker.color[0] == "#CE594B"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///secrets", "https://user:pass@example.test", None])
def test_context_rejects_non_web_urls(url):
    assert safe_link(url) is None


def test_context_date_range_parameters(monkeypatch):
    fetch = Mock(return_value=[])
    monkeypatch.setattr(repository, "_fetch", fetch)
    assert repository.get_dashboard_context("2024-11-21", "SEVEN") == {"news": [], "videos": []}
    for call in fetch.call_args_list:
        sql, parameters = call.args
        assert "2024-11-21" not in sql
        assert parameters == ("2024-11-21", "2024-11-22", "seven", 10)
    with pytest.raises(ValueError):
        repository.get_dashboard_context("2024-11-21", "CU", limit=1000)


def test_dashboard_interactions_without_network(monkeypatch, dashboard_rows):
    st = pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    monkeypatch.setattr(repository, "get_dashboard_sales", lambda: dashboard_rows)
    context = Mock(return_value={"news": [{"title": "Synthetic news", "url": "https://example.test/news"}], "videos": []})
    monkeypatch.setattr(repository, "get_dashboard_context", context)
    app = AppTest.from_file("streamlit_app.py").run(timeout=20)
    assert not app.exception
    assert len(app.metric) == 4
    assert len(app.get("plotly_chart")) == 6
    app.multiselect[0].set_value(["CU"]).run()
    assert not app.exception
    assert "CU" in app.metric[0].label
    assert context.call_args.args == ("2024-11-21", "CU")
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any("한 개 이상" in message.value for message in app.info)
    st.cache_data.clear()


def test_dashboard_url_selects_exact_event(monkeypatch, dashboard_rows):
    st = pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    monkeypatch.setattr(repository, "get_dashboard_sales", lambda: dashboard_rows)
    context = Mock(return_value={"news": [], "videos": []})
    monkeypatch.setattr(repository, "get_dashboard_context", context)
    app = AppTest.from_file("dashboard/streamlit_app.py")
    app.query_params.update(brand="CU", start="2024-11-21", end="2024-11-21", event="2024-11-21")
    app.run(timeout=20)
    assert not app.exception
    assert app.date_input[0].value == (date(2024, 11, 21), date(2024, 11, 21))
    assert context.call_args.args == ("2024-11-21", "CU")
    st.cache_data.clear()


def test_dashboard_database_error_does_not_expose_credentials(monkeypatch):
    st = pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    monkeypatch.setattr(repository, "get_dashboard_sales", Mock(side_effect=ValueError("synthetic-password")))
    app = AppTest.from_file("streamlit_app.py").run(timeout=20)
    assert not app.exception
    assert "synthetic-password" not in app.error[0].value
    st.cache_data.clear()


def test_simulation_dashboard_cannot_show_after_cutoff(monkeypatch, dashboard_rows):
    st = pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    for row in dashboard_rows:
        if row["store_type"] == "CU":
            row["growth_deviation"] = 2
    monkeypatch.setattr(repository, "get_dashboard_sales", lambda: dashboard_rows)
    monkeypatch.setattr(repository, "get_dashboard_context", lambda *args: {"news": [], "videos": []})
    app = AppTest.from_file("streamlit_app.py")
    app.query_params.update(brand="CU", start="2024-11-20", end="2024-11-22", as_of="2024-11-21")
    app.run(timeout=20)
    assert not app.exception
    assert app.date_input[0].value == (date(2024, 11, 20), date(2024, 11, 21))
    assert app.dataframe[0].value["날짜"].max().date() == date(2024, 11, 21)
    st.cache_data.clear()
