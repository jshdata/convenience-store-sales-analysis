"""DB 연결은 호출한 시점에만 생성하며 이전 서버의 기본값을 사용하지 않습니다."""

from contextlib import contextmanager
import ssl

from cv_store.config.settings import db_config, db_engine, source_db_config


def connect_db():
    config = db_config()
    if db_engine() == "postgresql":
        import pg8000.dbapi

        context = ssl.create_default_context(cafile=config.get("sslrootcert"))
        if config["sslmode"] != "verify-full":
            raise ValueError("Aiven PostgreSQL은 DB_SSLMODE=verify-full을 사용해주세요.")
        return pg8000.dbapi.connect(
            host=config["host"], port=config["port"], user=config["user"],
            password=config["password"], database=config["dbname"],
            timeout=config["connect_timeout"], ssl_context=context,
        )
    import pymysql

    return pymysql.connect(**config)


class _DictionaryCursor:
    """표준 DB-API 튜플 결과를 기존 Slack 코드의 dict 형태로 반환합니다."""

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, *args, **kwargs):
        self.cursor.execute(*args, **kwargs)
        return self

    def _row(self, row):
        return None if row is None else dict(zip((col[0] for col in self.cursor.description), row))

    def fetchone(self):
        return self._row(self.cursor.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self.cursor.fetchall()]


@contextmanager
def open_cursor(conn):
    """드라이버별 context manager 지원 차이를 숨기고 항상 커서를 닫습니다."""
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


@contextmanager
def dictionary_cursor(conn):
    if db_engine() == "postgresql":
        with open_cursor(conn) as cursor:
            yield _DictionaryCursor(cursor)
    else:
        import pymysql

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            yield cursor


@contextmanager
def source_connection():
    """일관된 읽기 전용 트랜잭션으로 원본 DB를 조회합니다."""
    import pymysql

    conn = pymysql.connect(**source_db_config())
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        yield conn
    finally:
        conn.rollback()
        conn.close()


@contextmanager
def connection():
    conn = connect_db()
    try:
        yield conn
    finally:
        conn.close()
