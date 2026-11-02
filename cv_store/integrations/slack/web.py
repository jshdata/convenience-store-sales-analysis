"""무료 웹 서비스의 시연용 진입점. 매출 데이터 API를 공개하지 않습니다."""

import atexit
import logging
from pathlib import Path
from threading import Lock, Thread

from flask import Flask, jsonify

from cv_store.config.settings import db_config
from cv_store.integrations.slack.app import create_app as create_slack_app
from cv_store.integrations.slack.check import validate_settings

logger = logging.getLogger(__name__)


def create_app(start_socket=True):
    app = Flask(__name__)
    state = {"handler": None, "status": "configuration_required"}
    app.extensions["slack_state"] = state
    issues, _ = validate_settings()
    if not issues:
        try:
            config = db_config()
            if config.get("sslmode") != "verify-full" or not Path(config.get("sslrootcert", "")).is_file():
                issues.append("서버용 Aiven CA 인증서 설정이 필요합니다.")
        except ValueError:
            issues.append("서버용 DB 설정이 필요합니다.")

    def connect():
        from slack_bolt.adapter.socket_mode import SocketModeHandler
        from cv_store.config.settings import require_env

        try:
            logger.warning("Slack startup: validating bot credentials")
            slack_app = create_slack_app()
            logger.warning("Slack startup: opening Socket Mode connection")
            handler = SocketModeHandler(slack_app, require_env("SLACK_APP_TOKEN"))
            state["handler"] = handler
            handler.connect()
            state["status"] = "connected"
            logger.warning("Slack Socket Mode connected")
        except Exception as exc:
            # 인증 응답/접속 문자열을 포함할 수 있는 예외 본문은 로그에 쓰지 않습니다.
            state["status"] = "connection_failed"
            logger.error("Slack startup failed (%s)", type(exc).__name__)

    def close():
        handler = state["handler"]
        if handler is not None:
            try:
                handler.close()
            except Exception as exc:
                logger.warning("Slack shutdown failed (%s)", type(exc).__name__)

    if not issues:
        state["status"] = "starting"
        if start_socket:
            atexit.register(close)
            startup_lock = Lock()
            state["startup_started"] = False

            @app.before_request
            def start_worker_socket():
                # Start after Gunicorn forks, inside the process serving HTTP.
                with startup_lock:
                    if not state["startup_started"]:
                        state["startup_started"] = True
                        Thread(target=connect, name="slack-socket-mode", daemon=True).start()
    else:
        logger.warning("Server configuration is incomplete; Slack connection not started")

    def result():
        handler = state["handler"]
        connected = bool(handler is not None and handler.client.is_connected())
        return {"service": "cstore-strategy-bot", "slack_connected": connected, "status": state["status"]}

    @app.get("/")
    def index():
        # 無料サービスの手動起動用。実データ/秘密情報は返しません。
        return jsonify(result())

    @app.get("/health")
    def health():
        status = result()
        return jsonify(status), 200 if status["slack_connected"] else 503

    return app
