"""날짜를 지정한 1회 검사. 이전의 자동 날짜 진행 시뮬레이션은 보관만 합니다."""

import argparse

from cv_store.config.settings import require_env
from cv_store.database.repository import validate_date
from cv_store.integrations.slack.notifications import send_anomaly_alerts


def main():
    parser = argparse.ArgumentParser(description="지정 날짜의 매출 이상치 Slack 알림 전송")
    parser.add_argument("--date", required=True, type=validate_date)
    args = parser.parse_args()
    from slack_sdk import WebClient

    client = WebClient(token=require_env("SLACK_BOT_TOKEN"))
    count = send_anomaly_alerts(client, require_env("SLACK_CHANNEL_ALERT"), args.date)
    print(f"전송된 이상 알림: {count}건 (동일 날짜 재실행 시 중복 발송 가능)")


if __name__ == "__main__":
    main()
