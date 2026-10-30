"""환경변수와 프로젝트 기준 경로. import 시 외부 연결이나 파일 생성을 하지 않습니다."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"필수 환경변수가 없습니다: {name} (.env.example 참고)")
    return value


def db_config():
    return {
        "host": require_env("DB_HOST"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": require_env("DB_USER"),
        "password": require_env("DB_PASSWORD"),
        "database": require_env("DB_NAME"),
        "charset": "utf8mb4",
        "connect_timeout": 10,
    }


def chrome_driver_path():
    # Selenium이 기본 드라이버 탐색을 하도록 미지정 시 None을 반환합니다.
    return os.environ.get("CHROMEDRIVER_PATH") or None


def slack_channels():
    return {
        name: os.environ.get(f"SLACK_CHANNEL_{name}", "").strip()
        for name in ("CU", "GS25", "SEVEN", "YOUTUBE", "NEWS", "ALERT", "TABLEAU")
    }
