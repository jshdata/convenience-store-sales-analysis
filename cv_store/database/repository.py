"""기존 DB 계약을 사용하는 조회. 테이블·뷰를 자동 생성하지 않습니다."""

from datetime import date, timedelta

from cv_store.config.settings import db_engine
from cv_store.database.connection import connection, dictionary_cursor

STORE_NAMES = {"CU": "CU", "GS25": "GS25", "SEVEN": "seven"}


def normalize_store(value):
    try:
        return STORE_NAMES[value.upper()]
    except (KeyError, AttributeError):
        raise ValueError("브랜드는 CU, GS25, SEVEN 중 하나여야 합니다.") from None


def validate_date(value):
    return date.fromisoformat(str(value)).isoformat()


def _fetch(sql, parameters):
    with connection() as conn:
        with dictionary_cursor(conn) as cursor:
            cursor.execute(sql, parameters)
            return cursor.fetchall()


def _date_text(column):
    # column은 이 모듈에서 고정한 이름만 전달하며 사용자 입력을 받지 않습니다.
    sql_type = "TEXT" if db_engine() == "postgresql" else "CHAR"
    return f"CAST({column} AS {sql_type})"


def get_sales_data(day, store):
    rows = _fetch(
        "SELECT sum_amount, sum_amount_growth, avg_sum_amount_growth, growth_deviation "
        "FROM all_sale WHERE sale_date = %s AND lower(store_type) = lower(%s)",
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
        f"WHERE lower(store_type) = lower(%s) AND {_date_text('published_at')} LIKE %s",
        (normalize_store(store), validate_date(day) + "%"),
    )
    return [row["video_url"] for row in rows]


def get_news_links_by_date_and_store(day, store):
    rows = _fetch(
        "SELECT news_url FROM news_search "
        f"WHERE lower(store_type) = lower(%s) AND {_date_text('news_date')} LIKE %s",
        (normalize_store(store), validate_date(day) + "%"),
    )
    return [row["news_url"] for row in rows]


def get_dashboard_sales():
    """대시보드용 일별 집계만 조회합니다. 인구통계 원자료는 반환하지 않습니다."""
    return _fetch(
        "SELECT sale_date, store_type, sum_amount, store_count, "
        "sum_amount_growth, avg_sum_amount_growth, growth_deviation "
        "FROM all_sale ORDER BY sale_date, store_type", (),
    )


def get_dashboard_context(day, store, limit=10):
    """같은 날짜·브랜드의 기사와 영상. 인과관계 추정이나 새 수집은 하지 않습니다."""
    start = date.fromisoformat(validate_date(day))
    end = start + timedelta(days=1)
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("조회 건수는 1~50이어야 합니다.")
    params = (start.isoformat(), end.isoformat(), normalize_store(store), limit)
    news = _fetch(
        "SELECT news_title AS title, news_url AS url, news_agency AS source "
        "FROM news_search WHERE news_date >= %s AND news_date < %s "
        "AND lower(store_type) = lower(%s) ORDER BY news_date, news_id LIMIT %s", params,
    )
    videos = _fetch(
        "SELECT video_title AS title, video_url AS url, channel_title AS source "
        "FROM ytb_video WHERE published_at >= %s AND published_at < %s "
        "AND lower(store_type) = lower(%s) ORDER BY published_at, video_id LIMIT %s", params,
    )
    return {"news": news, "videos": videos}
