"""고정 매출 Excel 전체 적재. 기본 실행은 미리보기이며 DB에 연결하지 않습니다."""

import argparse
from pathlib import Path

from cv_store.config.settings import DATA_DIR
from cv_store.database.connection import connection
from cv_store.database.repository import normalize_store

DEFAULT_SOURCE = DATA_DIR / "raw" / "sales" / "all.xlsx"
SALES_COLUMNS = ["sale_date", "sale", "store_count", "store_type"]


def load_sales(path=DEFAULT_SOURCE):
    import pandas as pd

    frame = pd.read_excel(path, header=None).dropna(how="all")
    if len(frame.columns) != len(SALES_COLUMNS):
        raise ValueError("매출 입력은 날짜·매출·점포 수·브랜드 4열이어야 합니다.")
    frame.columns = SALES_COLUMNS
    if frame.isna().any().any():
        raise ValueError("매출 필수 값이 비어 있습니다.")
    frame["sale_date"] = pd.to_datetime(frame["sale_date"], errors="raise").dt.date
    frame["store_type"] = frame["store_type"].map(normalize_store)
    for col in ("sale", "store_count"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if ((frame[col] < 0) | (frame[col] % 1 != 0)).any():
            raise ValueError(f"{col}는 0 이상의 정수여야 합니다.")
        frame[col] = frame[col].astype("int64")
    if frame.duplicated(["sale_date", "store_type"]).any():
        raise ValueError("입력에 날짜·브랜드 중복이 있습니다. 원본을 확인해주세요.")
    return frame.sort_values(["sale_date", "store_type"]).reset_index(drop=True)


def insert_sales(frame):
    """기존 sale만 사용. 동일 키는 같은 값일 때 생략, 충돌 시 전체 적재 중단."""
    with connection() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT sale_date, store_type, sale, store_count FROM sale")
                existing = {}
                for day, store, amount, count in cursor.fetchall():
                    key = (str(day)[:10], normalize_store(store))
                    if key in existing:
                        raise ValueError("기존 sale에 날짜·브랜드 중복이 있습니다. DB 점검이 필요합니다.")
                    existing[key] = (amount, count)
                rows = []
                for row in frame.itertuples(index=False):
                    key = (row.sale_date.isoformat(), row.store_type)
                    values = (int(row.sale), int(row.store_count))
                    if key in existing:
                        if existing[key] != values:
                            raise ValueError(f"기존 매출과 입력 값이 다릅니다: {key}")
                        continue
                    rows.append((row.store_type, *values, row.sale_date))
                if rows:
                    cursor.executemany(
                        "INSERT INTO sale (store_type, sale, store_count, sale_date) "
                        "VALUES (%s, %s, %s, %s)", rows,
                    )
            conn.commit()
            return len(rows)
        except Exception:
            conn.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description="전체 매출 Excel 검증·적재 (기본: 로컬 미리보기)")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--write", action="store_true", help="설정된 DB의 기존 sale에 적재")
    args = parser.parse_args()
    frame = load_sales(args.source)
    print(f"검증: {len(frame)}행, {frame.sale_date.min()} ~ {frame.sale_date.max()}")
    print(frame.groupby("store_type").size().to_string())
    if args.write:
        print(f"신규 적재: {insert_sales(frame)}행")
    else:
        print("미리보기 완료. DB 연결·적재 없음. 적재는 --write를 명시해야 합니다.")


if __name__ == "__main__":
    main()
