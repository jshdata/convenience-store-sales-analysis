import os
from unittest.mock import Mock

import pytest

from cv_store.config import settings
from cv_store.database import connection as db
from cv_store.database import inspect as inspection


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setattr(settings, "load_local_env", lambda: None)
    for key in list(os.environ):
        if key.startswith(("DB_", "SOURCE_DB_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in {
        "DB_HOST": "db.example.test", "DB_USER": "test_user",
        "DB_PASSWORD": "synthetic_password", "DB_NAME": "test_db",
    }.items():
        monkeypatch.setenv(key, value)


def test_postgresql_configuration_defaults(monkeypatch):
    monkeypatch.setenv("DB_SSLROOTCERT", "runtime/certs/test-ca.pem")
    cfg = settings.db_config()
    assert cfg["dbname"] == "test_db"
    assert cfg["port"] == 5432
    assert cfg["sslmode"] == "verify-full"
    assert cfg["sslrootcert"] == str(settings.PROJECT_ROOT / "runtime/certs/test-ca.pem")
    assert "charset" not in cfg and "database" not in cfg


def test_mysql_remains_supported(monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "mysql")
    cfg = settings.db_config()
    assert cfg["port"] == 3306
    assert cfg["database"] == "test_db"
    assert cfg["charset"] == "utf8mb4"
    assert "sslmode" not in cfg and "dbname" not in cfg


def test_unsupported_engine_and_unencrypted_mode_rejected(monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "unsupported")
    with pytest.raises(ValueError):
        settings.db_config()
    monkeypatch.setenv("DB_ENGINE", "postgresql")
    monkeypatch.setenv("DB_SSLMODE", "disable")
    with pytest.raises(ValueError):
        settings.db_config()


def test_connect_uses_selected_driver(monkeypatch):
    import pg8000.dbapi
    import pymysql

    postgres, mysql = Mock(), Mock()
    monkeypatch.setattr(pg8000.dbapi, "connect", postgres)
    monkeypatch.setattr(pymysql, "connect", mysql)
    assert db.connect_db() is postgres.return_value
    assert postgres.call_args.kwargs["ssl_context"].check_hostname is True
    assert postgres.call_args.kwargs["ssl_context"].verify_mode == __import__("ssl").CERT_REQUIRED
    mysql.assert_not_called()
    monkeypatch.setenv("DB_ENGINE", "mysql")
    assert db.connect_db() is mysql.return_value


def test_source_connection_is_read_only_and_always_rolls_back(monkeypatch):
    import pymysql

    monkeypatch.setenv("SOURCE_DB_USER", "local_test")
    conn, cursor = Mock(), Mock()
    conn.cursor.return_value.__enter__ = Mock(return_value=cursor)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(pymysql, "connect", Mock(return_value=conn))
    with pytest.raises(RuntimeError):
        with db.source_connection():
            raise RuntimeError("simulated failure")
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ",
        "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",
    ]
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_inspection_cli_does_not_print_driver_exception(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["inspect", "target"])
    monkeypatch.setattr(inspection, "inspect_target", Mock(side_effect=RuntimeError("private_example")))
    with pytest.raises(SystemExit):
        inspection.main()
    output = capsys.readouterr().out
    assert "private_example" not in output
    assert "RuntimeError" in output


def test_dictionary_cursor_maps_columns_and_null():
    raw = Mock(description=[("name",), ("count",)])
    raw.fetchone.side_effect = [("CU", 1), None]
    cursor = db._DictionaryCursor(raw)
    assert cursor.fetchone() == {"name": "CU", "count": 1}
    assert cursor.fetchone() is None
