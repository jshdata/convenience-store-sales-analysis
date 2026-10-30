"""원본 스키마 점검 및 PostgreSQL 접속 확인. 데이터를 수정하지 않습니다."""

import argparse
import json
from pathlib import Path

from cv_store.config.settings import PROJECT_ROOT, db_engine, source_db_config
from cv_store.database.connection import connection, dictionary_cursor, source_connection

SOURCE_REPORT = PROJECT_ROOT / "runtime" / "migration" / "source_schema.json"


def inspect_source():
    import pymysql

    schema = source_db_config()["database"]
    with source_connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT TABLE_NAME AS name, TABLE_TYPE AS type, ENGINE AS engine "
                "FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
                (schema,),
            )
            tables = cursor.fetchall()
            for table in tables:
                name = table["name"]
                cursor.execute(
                    "SELECT COLUMN_NAME AS name, DATA_TYPE AS data_type, COLUMN_TYPE AS column_type, "
                    "IS_NULLABLE AS nullable, COLUMN_DEFAULT AS default_value, EXTRA AS extra, "
                    "COLUMN_KEY AS column_key, NUMERIC_PRECISION AS numeric_precision, "
                    "NUMERIC_SCALE AS numeric_scale, CHARACTER_MAXIMUM_LENGTH AS max_length, "
                    "GENERATION_EXPRESSION AS generation_expression "
                    "FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                    (schema, name),
                )
                table["columns"] = cursor.fetchall()
                cursor.execute(
                    "SELECT INDEX_NAME AS name, NON_UNIQUE AS non_unique, COLUMN_NAME AS column_name, "
                    "SEQ_IN_INDEX AS position FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY INDEX_NAME, SEQ_IN_INDEX",
                    (schema, name),
                )
                table["indexes"] = cursor.fetchall()
                # DB에서 반환한 식별자만 사용하고 백틱을 이스케이프합니다.
                quoted = "`" + name.replace("`", "``") + "`"
                cursor.execute(f"SELECT COUNT(*) AS row_count FROM {quoted}")
                table["row_count"] = cursor.fetchone()["row_count"]
            cursor.execute(
                "SELECT TRIGGER_NAME AS name, EVENT_OBJECT_TABLE AS table_name, "
                "ACTION_TIMING AS timing, EVENT_MANIPULATION AS event, ACTION_STATEMENT AS statement "
                "FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = %s",
                (schema,),
            )
            triggers = cursor.fetchall()
            cursor.execute(
                "SELECT TABLE_NAME AS name, VIEW_DEFINITION AS definition "
                "FROM information_schema.VIEWS WHERE TABLE_SCHEMA = %s", (schema,),
            )
            views = cursor.fetchall()
            cursor.execute(
                "SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name, "
                "REFERENCED_TABLE_NAME AS referenced_table, REFERENCED_COLUMN_NAME AS referenced_column "
                "FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL", (schema,),
            )
            foreign_keys = cursor.fetchall()
    return {"database": schema, "tables": tables, "triggers": triggers, "views": views, "foreign_keys": foreign_keys}


def inspect_target():
    if db_engine() != "postgresql":
        raise ValueError("대상 점검에는 DB_ENGINE=postgresql이 필요합니다.")
    with connection() as conn:
        with dictionary_cursor(conn) as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                "SELECT current_database() AS database, current_setting('server_version') AS version"
            )
            result = cursor.fetchone()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            result["tables"] = [row["table_name"] for row in cursor.fetchall()]
            cursor.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            result["ssl"] = cursor.fetchone()["ssl"]
    return result


def main():
    parser = argparse.ArgumentParser(description="읽기 전용 DB 점검. 인증 정보·실제 행은 출력하지 않습니다.")
    parser.add_argument("database", choices=("source", "target"))
    args = parser.parse_args()
    try:
        if args.database == "source":
            report = inspect_source()
            SOURCE_REPORT.parent.mkdir(parents=True, exist_ok=True)
            SOURCE_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
            print(f"원본 스키마 저장: {SOURCE_REPORT.relative_to(PROJECT_ROOT)}")
            for table in report["tables"]:
                print(f"{table['name']}: {table['row_count']}행, {len(table['columns'])}열 ({table['type']})")
            print(f"트리거 {len(report['triggers'])}개, 뷰 {len(report['views'])}개. 원본 변경 없음.")
        else:
            print(json.dumps(inspect_target(), ensure_ascii=False, default=str))
    except Exception as exc:
        # 드라이버 예외 문자열에는 접속 정보가 들어갈 수 있어 그대로 출력하지 않습니다.
        print(f"DB 점검 실패 ({type(exc).__name__}). .env 접속값·실행 상태·CA 인증서를 확인해주세요.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
