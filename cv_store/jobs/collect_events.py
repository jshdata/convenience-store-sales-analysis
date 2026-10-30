"""수집 작업과 예약 실행 분리. 기본은 1회, --daily를 지정하면 기존 주기 사용."""

import argparse
import importlib
import time

COLLECTORS = {
    "cu": ("cu_events", "run_script", "13:22"),
    "gs25": ("gs25_events", "scrape_gs25_events", "11:30"),
    "seven": ("seven_events", "run_crawling", "00:00"),
    "promotions": ("promotions", "check_and_run_crawling", "11:49"),
}


def main():
    parser = argparse.ArgumentParser(description="행사 수집기 실행")
    parser.add_argument("collector", choices=COLLECTORS)
    parser.add_argument("--daily", action="store_true", help="호스트 현지 시간 기준 예약 실행")
    args = parser.parse_args()
    module_name, function_name, clock = COLLECTORS[args.collector]
    job = getattr(importlib.import_module(f"cv_store.collectors.{module_name}"), function_name)
    if not args.daily:
        job()
        return
    import schedule

    scheduler = schedule.Scheduler()
    scheduler.every().day.at(clock).do(job)
    while True:
        scheduler.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
