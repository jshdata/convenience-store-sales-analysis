"""Slack 설정 확인. 기본은 오프라인, --online도 메시지를 전송하지 않습니다."""

import argparse
import os
import re

from cv_store.config.settings import load_local_env, slack_channels


def validate_settings():
    load_local_env()
    issues = []
    for name, prefix in (("SLACK_BOT_TOKEN", "xoxb-"), ("SLACK_APP_TOKEN", "xapp-")):
        value = os.environ.get(name, "").strip()
        if not value:
            issues.append(f"{name}: 미입력")
        elif not value.startswith(prefix):
            issues.append(f"{name}: 토큰 종류 확인 필요")
    channels = {name: value for name, value in slack_channels().items() if value}
    if not channels:
        issues.append("SLACK_CHANNEL_*: 사용할 채널을 최소 하나 입력해야 합니다.")
    for name, value in channels.items():
        if not re.fullmatch(r"[CG][A-Z0-9]{8,}", value):
            issues.append(f"SLACK_CHANNEL_{name}: 채널 이름이 아닌 채널 ID를 입력해주세요.")
    if len(channels.values()) != len(set(channels.values())):
        issues.append("SLACK_CHANNEL_*: 기능별 채널 ID가 중복되었습니다.")
    return issues, list(channels)


def check_online():
    from slack_sdk import WebClient

    # API 응답의 URL/토큰/프로필은 출력하거나 저장하지 않습니다.
    WebClient(token=os.environ["SLACK_BOT_TOKEN"].strip(), timeout=15).auth_test()
    WebClient(timeout=15).apps_connections_open(app_token=os.environ["SLACK_APP_TOKEN"].strip())


def main():
    parser = argparse.ArgumentParser(description="Slack 토큰·채널 설정 확인 (비밀값 출력 없음)")
    parser.add_argument("--online", action="store_true", help="봇 인증 및 Socket Mode URL 발급 확인. 메시지 전송 없음.")
    args = parser.parse_args()
    issues, channels = validate_settings()
    if issues:
        for issue in issues:
            print(issue)
        raise SystemExit(1)
    print("로컬 설정 형식 확인 완료. 채널 종류: " + ", ".join(channels))
    if args.online:
        try:
            check_online()
        except Exception as exc:
            from slack_sdk.errors import SlackApiError

            # 오류 본문에는 토큰이나 연결 URL이 포함될 수 있습니다.
            if isinstance(exc, SlackApiError):
                code = exc.response.get("error", "unknown_error")
                print("Slack 인증 실패: " + (code if re.fullmatch(r"[a-z_]+", str(code)) else "unknown_error"))
            else:
                print(f"Slack 연결 실패 ({type(exc).__name__}). 네트워크·설정을 확인해주세요.")
            raise SystemExit(1) from None
        print("봇 인증과 Socket Mode 연결 준비 확인 완료. 메시지 전송 없음.")


if __name__ == "__main__":
    main()
