"""명시적으로 실행할 때만 Slack 연결. 앱·워크스페이스를 생성하지 않습니다."""

from cv_store.config.settings import require_env, slack_channels
from cv_store.integrations.slack.handlers import register_handlers


def create_app():
    from slack_bolt import App

    token = require_env("SLACK_BOT_TOKEN")
    channels = slack_channels()
    configured = [value for value in channels.values() if value]
    if not configured:
        raise ValueError("최소 하나의 SLACK_CHANNEL_* 설정이 필요합니다.")
    if len(configured) != len(set(configured)):
        raise ValueError("기능별 Slack 채널 ID는 중복될 수 없습니다.")
    app = App(token=token)
    register_handlers(app, channels)
    return app


def main():
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app_token = require_env("SLACK_APP_TOKEN")
    SocketModeHandler(create_app(), app_token).start()


if __name__ == "__main__":
    main()
