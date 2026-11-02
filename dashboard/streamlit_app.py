"""Community Cloud 진입점. 이 폴더의 requirements.txt를 우선 사용합니다."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cv_store.dashboard.app import main

if __name__ == "__main__":
    main()
