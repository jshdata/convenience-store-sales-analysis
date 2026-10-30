"""환경변수와 프로젝트 기준 경로. import 시 외부 연결이나 파일 생성을 하지 않습니다."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def require_env(name):
    load_local_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"필수 환경변수가 없습니다: {name} (.env.example 참고)")
    return value


def load_local_env():
    """로컬 .env만 읽으며 프로세스에 이미 지정된 설정은 덮어쓰지 않습니다."""
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)


def db_engine():
    load_local_env()
    engine = os.environ.get("DB_ENGINE", "postgresql").lower()
    if engine not in {"postgresql", "mysql"}:
        raise ValueError("DB_ENGINE은 postgresql 또는 mysql이어야 합니다.")
    return engine


def db_config():
    engine = db_engine()
    config = {
        "host": require_env("DB_HOST"),
        "port": int(os.environ.get("DB_PORT") or ("5432" if engine == "postgresql" else "3306")),
        "user": require_env("DB_USER"),
        "password": require_env("DB_PASSWORD"),
        "connect_timeout": 10,
    }
    if engine == "postgresql":
        mode = os.environ.get("DB_SSLMODE") or "verify-full"
        if mode not in {"verify-full", "verify-ca", "require"}:
            raise ValueError("PostgreSQL 연결에는 SSL 인증이 필요합니다.")
        config.update(dbname=require_env("DB_NAME"), sslmode=mode)
        ca = os.environ.get("DB_SSLROOTCERT", "").strip()
        if ca:
            path = Path(ca)
            config["sslrootcert"] = str(path if path.is_absolute() else PROJECT_ROOT / path)
    else:
        config.update(database=require_env("DB_NAME"), charset="utf8mb4")
    return config


def source_db_config():
    """이전 원본 MariaDB 전용. 대상 DB 인증 정보와 분리합니다."""
    load_local_env()
    return {
        "host": os.environ.get("SOURCE_DB_HOST") or "127.0.0.1",
        "port": int(os.environ.get("SOURCE_DB_PORT") or "3306"),
        "user": require_env("SOURCE_DB_USER"),
        # 비밀번호 없는 로컬 계정도 명시적인 빈 값으로 사용할 수 있습니다.
        "password": os.environ.get("SOURCE_DB_PASSWORD", ""),
        "database": os.environ.get("SOURCE_DB_NAME") or "crawling",
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
