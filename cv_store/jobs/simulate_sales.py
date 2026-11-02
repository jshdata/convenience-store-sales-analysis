"""날짜 범위의 이상치 미리보기 전용 CLI. DB 쓰기와 Slack 발송 없음."""

import argparse
import json

from cv_store.simulation.service import preview, InputError


def main():
    parser = argparse.ArgumentParser(description="기간 지정 이상치 시뮬레이션 미리보기 (발송 없음)")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--store", default="ALL", choices=["ALL", "CU", "GS25", "SEVEN"])
    args = parser.parse_args()
    print(json.dumps(preview(args.start, args.end, args.store), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except InputError as exc:
        print(str(exc))
        raise SystemExit(1) from None
    except Exception as exc:
        print(f"미리보기 실패 ({type(exc).__name__}). DB 설정을 확인해주세요.")
        raise SystemExit(1) from None
