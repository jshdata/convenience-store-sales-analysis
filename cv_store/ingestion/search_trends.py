"""검색 트렌드 CSV 전체 적재. 뉴스 크롤러나 하루 단위 시뮬레이션이 아닙니다."""

import argparse
from pathlib import Path

from cv_store.config.settings import DATA_DIR
from cv_store.database.connection import connection, open_cursor

DEFAULT_SOURCE = DATA_DIR / "raw" / "search_trends" / "trend_data2.csv"


def load_search_trends(path=DEFAULT_SOURCE):
    import pandas as pd

    frame = pd.read_csv(path, header=None, encoding="utf-8-sig").dropna(how="all")
    if len(frame.columns) != 5:
        raise ValueError("검색 트렌드 입력은 날짜·seven·GS25·CU·cs 5열이어야 합니다.")
    frame.columns = ["DATE", "seven", "GS25", "CU", "cs"]
    if frame.isna().any().any():
        raise ValueError("검색 트렌드 필수 값이 비어 있습니다.")
    frame["DATE"] = pd.to_datetime(frame["DATE"], errors="raise").dt.date
    for col in ("seven", "GS25", "CU", "cs"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    if frame.duplicated("DATE").any():
        raise ValueError("검색 트렌드 입력에 날짜 중복이 있습니다.")
    return frame.sort_values("DATE").reset_index(drop=True)


def insert_search_trends(frame):
    with connection() as conn:
        try:
            with open_cursor(conn) as cursor:
                cursor.execute("SELECT trend_date, seven, gs25, cu, cs FROM naver_search_trend")
                existing = {}
                for day, *values in cursor.fetchall():
                    key = str(day)[:10]
                    if key in existing:
                        raise ValueError("기존 검색 트렌드에 날짜 중복이 있습니다.")
                    existing[key] = tuple(float(value) for value in values)
                rows = []
                for row in frame.itertuples(index=False, name=None):
                    day, *values = row
                    key = day.isoformat()
                    if key in existing:
                        if any(abs(a - float(b)) > 1e-6 for a, b in zip(existing[key], values)):
                            raise ValueError(f"기존 검색 트렌드와 입력 값이 다릅니다: {key}")
                        continue
                    rows.append((day, *values))
                if rows:
                    cursor.executemany(
                        "INSERT INTO naver_search_trend (trend_date, seven, gs25, cu, cs) "
                        "VALUES (%s, %s, %s, %s, %s)", rows,
                    )
            conn.commit()
            return len(rows)
        except Exception:
            conn.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description="전체 검색 트렌드 검증·적재 (기본: 로컬 미리보기)")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    frame = load_search_trends(args.source)
    print(f"검증: {len(frame)}행, {frame.DATE.min()} ~ {frame.DATE.max()}")
    if args.write:
        print(f"신규 적재: {insert_search_trends(frame)}행")
    else:
        print("미리보기 완료. DB 연결·적재 없음. 적재는 --write를 명시해야 합니다.")


if __name__ == "__main__":
    main()
