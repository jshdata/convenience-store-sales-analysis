"""기존 DB 계약을 사용하는 조회. 테이블·뷰를 자동 생성하지 않습니다."""

from datetime import date

from cv_store.database.connection import connection

STORE_NAMES = {"CU": "CU", "GS25": "GS25", "SEVEN": "seven"}


def normalize_store(value):
    try:
        return STORE_NAMES[value.upper()]
    except (KeyError, AttributeError):
        raise ValueError("브랜드는 CU, GS25, SEVEN 중 하나여야 합니다.") from None


def validate_date(value):
    return date.fromisoformat(str(value)).isoformat()


def _fetch(sql, parameters):
    import pymysql

    with connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, parameters)
            return cursor.fetchall()


def get_sales_data(day, store):
    rows = _fetch(
        "SELECT sum_amount, sum_amount_growth, avg_sum_amount_growth, growth_deviation "
        "FROM all_sale WHERE sale_date = %s AND store_type = %s",
        (validate_date(day), normalize_store(store)),
    )
    return rows[0] if rows else None


def get_sales_for_date(day):
    return _fetch(
        "SELECT sale_date, store_type, sum_amount, growth_deviation "
        "FROM all_sale WHERE sale_date = %s",
        (validate_date(day),),
    )


def get_ytb_links_by_date_and_store(day, store):
    rows = _fetch(
        "SELECT video_url FROM ytb_video "
        "WHERE store_type = %s AND published_at LIKE %s",
        (normalize_store(store), validate_date(day) + "%"),
    )
    return [row["video_url"] for row in rows]


def get_news_links_by_date_and_store(day, store):
    rows = _fetch(
        "SELECT news_url FROM news_search "
        "WHERE store_type = %s AND news_date LIKE %s",
        (normalize_store(store), validate_date(day) + "%"),
    )
    return [row["news_url"] for row in rows]
