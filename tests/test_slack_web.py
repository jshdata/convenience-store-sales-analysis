from unittest.mock import Mock

from cv_store.integrations.slack import web


def test_unconfigured_web_does_not_connect_or_expose_sales(monkeypatch):
    monkeypatch.setattr(web, "validate_settings", lambda: (["missing"], []))
    create = Mock()
    monkeypatch.setattr(web, "create_slack_app", create)
    app = web.create_app()
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 503
    assert client.get("/sale").status_code == 404
    assert client.get("/test-db").status_code == 404
    create.assert_not_called()


def test_health_requires_live_socket(monkeypatch, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("synthetic-public-ca", encoding="utf-8")
    monkeypatch.setattr(web, "validate_settings", lambda: ([], ["CU"]))
    monkeypatch.setattr(web, "db_config", lambda: {"sslmode": "verify-full", "sslrootcert": str(ca)})
    app = web.create_app(start_socket=False)
    handler = Mock()
    handler.client.is_connected.return_value = True
    app.extensions["slack_state"].update(handler=handler, status="connected")
    assert app.test_client().get("/health").status_code == 200
    handler.client.is_connected.return_value = False
    assert app.test_client().get("/health").status_code == 503


def test_socket_starts_once_in_serving_process(monkeypatch, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("synthetic-public-ca", encoding="utf-8")
    monkeypatch.setattr(web, "validate_settings", lambda: ([], ["CU"]))
    monkeypatch.setattr(web, "db_config", lambda: {"sslmode": "verify-full", "sslrootcert": str(ca)})
    thread = Mock()
    monkeypatch.setattr(web, "Thread", thread)
    app = web.create_app()
    thread.assert_not_called()
    client = app.test_client()
    client.get("/health")
    client.get("/")
    thread.assert_called_once()
    thread.return_value.start.assert_called_once()
