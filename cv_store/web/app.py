"""선택적 매출 조회 API. DB 연결은 요청 시에만 생성합니다."""

import logging

from cv_store.database.connection import connection

logger = logging.getLogger(__name__)
SALE_COLUMNS = (
    "id_sale", "sale_date", "store_count", "sum_amount", "store_type",
    "man10", "man20", "man30", "man40", "man50", "man60",
    "woman10", "woman20", "woman30", "woman40", "woman50", "woman60", "day", "kind_day",
)


def create_app():
    import pymysql
    from flask import Flask, jsonify

    app = Flask(__name__)

    @app.get("/sale")
    def get_sale_data():
        try:
            with connection() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute("SELECT " + ", ".join(SALE_COLUMNS) + " FROM all_sale")
                    rows = cursor.fetchall()
            return jsonify({"status": "success", "sale_data": rows})
        except Exception:
            logger.exception("매출 API 조회 실패")
            return jsonify({"status": "error", "message": "Database query failed"}), 503

    @app.get("/test-db")
    def test_db():
        # 기존 진단 기능은 명시적으로 활성화한 로컬 점검에서만 제공합니다.
        if not app.config.get("ENABLE_DB_DIAGNOSTICS", False):
            return jsonify({"status": "error", "message": "Not found"}), 404
        try:
            with connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SHOW TABLES")
                    tables = cursor.fetchall()
            return jsonify({"status": "success", "tables": tables})
        except Exception:
            logger.exception("DB 진단 실패")
            return jsonify({"status": "error", "message": "Database query failed"}), 503

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
