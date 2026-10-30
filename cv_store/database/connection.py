"""DB 연결은 호출한 시점에만 생성하며 이전 서버의 기본값을 사용하지 않습니다."""

from contextlib import contextmanager

from cv_store.config.settings import db_config


def connect_db():
    import pymysql

    return pymysql.connect(**db_config())


@contextmanager
def connection():
    conn = connect_db()
    try:
        yield conn
    finally:
        conn.close()
