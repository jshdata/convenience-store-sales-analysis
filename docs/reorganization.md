# 구조 정리 결과

## 기준과 의사결정

기준은 정리 전 로컬 저장소와 사용자 설명입니다.
원래 파일 49개는 Python 20개, 데이터·상태 13개, 웹 리소스 8개, 캐시 8개였습니다.

핵심 기능은 매출 이상 판정·Slack 알림·브랜드별 매출 조회·관련 뉴스/영상 조회·Tableau 링크 제공입니다.
매출 예측은 실제 시연 후 성능 문제로 제외한 실험이며 향후 모델링 과제로 분리합니다.
Flask 회원가입·예시 홈 화면은 핵심 기능과 연결되지 않아 시제품으로 보관했습니다.
기존 `/sale` JSON API는 선택적 웹 모듈로 유지합니다.

일별 매출 적재는 실시간 수집이 아니라 과거 데이터 유입 시뮬레이션이었습니다.
현재는 전체 파일 적재를 준비하고, 자동 날짜 진행·재생은 추후 별도 설계합니다.
따라서 `sale_schedule.py`와 `naver_schedule.py`를 실제 수집기로 이름만 바꾸지 않았습니다.

## 분리한 책임

| 책임 | 현재 위치 |
|---|---|
| 환경변수·경로 | `cv_store/config/settings.py` |
| DB 연결·조회 | `cv_store/database/connection.py`, `repository.py` |
| CU·GS25·Seven·증정 행사 | `cv_store/collectors/` |
| 고정 매출·트렌드 전체 적재 | `cv_store/ingestion/` |
| 매출 이상 판정 | `cv_store/analysis/anomalies.py` |
| Slack 앱·입력·메시지·발송 | `cv_store/integrations/slack/` |
| 수집 예약·날짜별 검사 실행 | `cv_store/jobs/` |
| 기존 매출 JSON API | `cv_store/web/app.py` |
| 과거 코드와 불명확한 기능 | `archive/` |

독립 역할의 파일 적재기와 외부 사이트 수집기를 구분했습니다.
루트 패키지 `cv_store`를 사용해 외부 `slack` 라이브러리와의 이름 혼동을 없앴습니다.
데이터 경로는 프로젝트 위치를 기준으로 계산하며 사용자별 Windows/Linux 절대 경로를 제거했습니다.

## 함수·의존성

직접 연결은 다음과 같습니다. 화살표는 함수 호출·import 의존입니다.

```text
jobs/collect_events → collectors/* → database/connection → config/settings
ingestion/* → database/connection
jobs/anomaly_alerts → slack/notifications → analysis/anomalies
                                       → database/repository
                                       → slack/messages
slack/app → slack/handlers → database/repository + slack/messages
web/app → database/connection
```

- 수집기: CU `run_script`, GS25 `scrape_gs25_events`, Seven `run_crawling`, 증정 `check_and_run_crawling`.
- 적재기: `load_sales`/`insert_sales`, `load_search_trends`/`insert_search_trends`. 파일 검증과 DB 쓰기 분리.
- 조회: `get_sales_data`, `get_sales_for_date`, `get_ytb_links_by_date_and_store`, `get_news_links_by_date_and_store`.
- 판정: `classify_anomaly`. DB·Slack 연결 없이 입력 값만 비교.
- Slack: `create_app`, `register_handlers`, `handle_mention`, `handle_more`, `send_anomaly_alerts`.
- 메시지: 기존 `format_news_links`, `format_ytb_links`를 분리해 버튼 action ID 보존.

사용자 정의 클래스는 원래 없었으며 이번 정리에서도 불필요하게 도입하지 않았습니다.

## 중복 처리와 동작 변경

- `final.py`·`sale_slack.py`·`slack.py`의 중복을 활성 Slack 모듈과 과거 예측 참고본으로 분리.
- 같은 파일에 중복 정의된 `format_ytb_links` 제거. 마지막 정의의 구현 보존.
- 장기간 공유하던 DB 연결을 작업별 연결로 변경하고 사용자 입력 SQL을 파라미터화.
- import 시 연결·브라우저 실행·무한 루프·모델 로딩을 제거.
- 기존 임계값과 날짜/브랜드 관련 링크 연결 방식 보존.
- `all.xlsx`와 `trend_data2.csv`의 첫 행이 헤더로 소비되던 문제 수정.
- 매출 전체 적재는 한 트랜잭션으로 실행하며 기존 키와 값 충돌 시 중단.
- CU `MAX(idx)`에 CU 브랜드 조건 추가.
- 증정 행사 수집이 기존 날짜를 만났을 때 누적한 새 항목을 저장하기 전에 반환하던 문제 수정.
- GS25 브라우저는 실행 시 생성하고 종료 시 정리. Seven 요소를 상세 화면 왕복마다 다시 조회.
- 회원가입 시제품 JavaScript의 비밀번호 콘솔 출력 제거.
- `/sale`은 튜플 위치 대신 열 이름으로 조회, 오류 상세 비노출. `/test-db`는 명시적 로컬 진단만 허용.

## 유지·이동·통합·삭제 검토

| 원래 파일 | 분류와 결과 |
|---|---|
| `CU_schedule.py`, `GS25_schedule.py`, `seven_schedule.py`, `plus_schedule.py` | 이동·통합: 브랜드 수집과 공통 실행 분리, 설정 제거된 참고본 보존 |
| `sale_slack.py` | 통합: 조회·알림·버튼·Tableau 기능 분리, 참고본 보존 |
| `final.py`, `slack.py` | 통합·보관: 핵심 Slack과 예측 분리. 원래 예측 구현 보존 |
| `sale_schedule.py`, `naver_schedule.py`, `csvtodb.py` | 통합·보관: 과거 시뮬레이션 이름 명확화, 현재는 파일 전체 적재 |
| `db.py` | 통합: 환경변수 기반 공통 연결 |
| `app.py` | 이동: 매출 API 유지, 화면·회원 부분은 보관 |
| `routes/*` | 삭제 검토·보관: 회원 기능 및 예시 홈 화면은 현재 실행 경로에서 제외 |
| `cu.py`, `webcrollingtwo.py` | 삭제 검토·보관: 역사 수집/페이지 이동 버전. 범위 차이 때문에 삭제하지 않음 |
| `as.py`, `cl.py`, `crawl.py` | 삭제 검토·보관: 현재 흐름과 연결 안 된 실험 |
| 원본·가공 CSV/Excel | 유지·이동: 직접 참조가 없어도 데이터 근거로 보존 |
| 두 체크포인트 | 이동·보관: 값은 같지만 서로 다른 시뮬레이션 상태 |
| Bootstrap 일반·압축본 및 폰트 | 이동·보관: 시제품 리소스 유지 |
| `.pyc` 8개 | 삭제: 과거 인증 정보 잔존 가능성 제거. 현재 서비스에서 사용하지 않는 `ai_route` 캐시도 포함 |

Git 관리 파일을 제외한 원래 데이터·리소스를 임의 삭제하지 않았습니다.
기존 Python 파일은 새 모듈로 역할을 옮기고 설정을 가린 텍스트 참고본도 보관했습니다.
단순 파일 이동이 아닌 소스 변경은 Git 이력과 이 문서, 대응표로 추적합니다.

## 남은 작업

로컬 DB 구조와 실제 Tableau 연결 방식, 뉴스/영상 적재 과정 확인이 우선입니다.
서버·Slack 새 환경 구성 및 실통합 검증, 모델링·시뮬레이션 재설계는 이번 작업에 포함하지 않았습니다.
상세 제약과 운영 순서는 [operations.md](operations.md), 데이터는 [data_dictionary.md](data_dictionary.md)를 참고하세요.

## 공개 데이터 정책

원본 CSV·Excel, 가공 데이터, DB 백업과 기존 체크포인트는 로컬에 보존하되 GitHub에는 올리지 않습니다.
`data/README.md`와 출처·DB 계약 설명만 공개합니다. 과거 커밋에 있는 데이터는 `.gitignore`로 제거되지 않으며
공개 브랜치는 과거 커밋과 연결되지 않는 새 기준으로 게시합니다. 아래 대응표는 로컬 이동 이력을 뜻하며 공개 파일 목록은 아닙니다.

## 전체 파일 대응표

아래 표와 기계 판독 가능한 [file_manifest.json](file_manifest.json)은 원래 49개 파일의 위치를 기록합니다.

| 이전 경로 | 보존 위치 | 현재 실행 코드 |
|---|---|---|
| `all.xlsx` | `data/raw/sales/all.xlsx` | — |
| `sale_gender_age.xlsx` | `data/raw/sales/sale_gender_age.xlsx` | — |
| `cu.csv` | `data/raw/youtube/cu_videos.csv` | — |
| `gs25.csv` | `data/raw/youtube/gs25_videos.csv` | — |
| `7_1.csv` | `data/raw/youtube/seven_videos.csv` | — |
| `cu_table.csv` | `data/raw/youtube/cu_channels.csv` | — |
| `gs25_table.csv` | `data/raw/youtube/gs25_channels.csv` | — |
| `gs25_1.csv` | `data/interim/youtube/gs25_videos_with_store.csv` | — |
| `3store_data.CSV` | `data/interim/events/three_store_events.csv` | — |
| `trend_data2.csv` | `data/raw/search_trends/trend_data2.csv` | — |
| `중복된 video_id.xlsx` | `data/reference/duplicate_video_ids.xlsx` | — |
| `last_insert_date.txt` | `archive/simulation/state/sales_last_insert_date.txt` | — |
| `last_insert_date_naver.txt` | `archive/simulation/state/search_trends_last_insert_date.txt` | — |
| `final.py` | `archive/prediction/combined_prediction_bot.py.txt` | Core Slack extracted; prediction archived |
| `slack.py` | `archive/prediction/prediction_bot.py.txt` | — |
| `sale_schedule.py` | `archive/simulation/replay_sales_daily.py.txt` | cv_store/ingestion/sales.py (full-file ingestion; simulation archived) |
| `naver_schedule.py` | `archive/simulation/replay_search_trends_daily.py.txt` | cv_store/ingestion/search_trends.py (full-file ingestion) |
| `csvtodb.py` | `archive/simulation/seed_sales_before_2025.py.txt` | cv_store/ingestion/sales.py (full-file ingestion) |
| `sale_slack.py` | `archive/legacy/sales_slack_bot.py.txt` | cv_store/integrations/slack/ + cv_store/analysis/ + cv_store/database/ |
| `webcrollingtwo.py` | `archive/collectors/gs25_paginated.py.txt` | — |
| `cu.py` | `archive/collectors/cu_historical_csv.py.txt` | — |
| `as.py` | `archive/experiments/naver_shopping_api.py.txt` | — |
| `cl.py` | `archive/experiments/pyony_cu_sample.py.txt` | — |
| `crawl.py` | `archive/experiments/selenium_smoke.py.txt` | — |
| `CU_schedule.py` | `archive/legacy/CU_schedule.py.txt` | cv_store/collectors/cu_events.py + cv_store/jobs/collect_events.py |
| `GS25_schedule.py` | `archive/legacy/GS25_schedule.py.txt` | cv_store/collectors/gs25_events.py + cv_store/jobs/collect_events.py |
| `seven_schedule.py` | `archive/legacy/seven_schedule.py.txt` | cv_store/collectors/seven_events.py + cv_store/jobs/collect_events.py |
| `plus_schedule.py` | `archive/legacy/plus_schedule.py.txt` | cv_store/collectors/promotions.py + cv_store/jobs/collect_events.py |
| `app.py` | `archive/legacy/app.py.txt` | cv_store/web/app.py (JSON API only) |
| `db.py` | `archive/legacy/db.py.txt` | cv_store/database/connection.py |
| `routes/__init__.py` | `archive/legacy/routes___init__.py.txt` | — |
| `routes/view_route.py` | `archive/legacy/routes_view_route.py.txt` | — |
| `routes/user_route.py` | `archive/legacy/routes_user_route.py.txt` | — |
| `routes/__pycache__/ai_route.cpython-311.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `routes/__pycache__/ai_route.cpython-313.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `routes/__pycache__/user_route.cpython-311.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `routes/__pycache__/user_route.cpython-313.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `routes/__pycache__/view_route.cpython-311.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `routes/__pycache__/view_route.cpython-313.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `routes/__pycache__/__init__.cpython-311.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `routes/__pycache__/__init__.cpython-313.pyc` | 삭제 완료 (인증 정보 잔존 방지) | — |
| `templates/index.html` | `archive/web_prototype/templates/index.html` | — |
| `templates/save-user.html` | `archive/web_prototype/templates/save-user.html` | — |
| `static/css/bootstrap.css` | `archive/web_prototype/static/css/bootstrap.css` | — |
| `static/css/bootstrap.min.css` | `archive/web_prototype/static/css/bootstrap.min.css` | — |
| `static/css/style.css` | `archive/web_prototype/static/css/style.css` | — |
| `static/font/NotoSansKR-Regular.ttf` | `archive/web_prototype/static/font/NotoSansKR-Regular.ttf` | — |
| `static/font/NotoSansKR-Black.ttf` | `archive/web_prototype/static/font/NotoSansKR-Black.ttf` | — |
| `static/js/save-user.js` | `archive/web_prototype/static/js/save-user.js` | — |
