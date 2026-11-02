"""명시적으로 실행할 때만 simulation 스키마를 생성합니다."""

from cv_store.config.settings import PROJECT_ROOT
from cv_store.simulation.store import transaction


def main():
    sql = (PROJECT_ROOT / "database/schema/simulation.sql").read_text(encoding="utf-8")
    with transaction() as cur:
        for statement in sql.split(";"):
            if statement.strip():
                cur.execute(statement)
    print("simulation 실행·발송 이력 테이블 준비 완료. 원본 매출 테이블은 변경하지 않았습니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"시뮬레이션 테이블 준비 실패 ({type(exc).__name__}). DB 설정을 확인해주세요.")
        raise SystemExit(1) from None
