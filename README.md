# 편의점 3사 매출 이상 탐지 및 트렌드 분석

CU·GS25·세븐일레븐의 과거 매출에서 이상 변동을 확인하고, 같은 날짜·브랜드의
뉴스와 유튜브 링크를 Slack에서 조회하는 팀 프로젝트입니다. Tableau 대시보드 링크도 제공합니다.

매출 분석에는 프로젝트 수행 당시 멘토를 통해 제공받은 약 1년 분량의 비식별 카드 결제 기반
편의점 매출 집계 데이터를 활용했습니다. 일자·브랜드별 총매출 및 성별·연령대별 매출을 분석에 사용했습니다.
원천 제공기관과 구체적인 비식별 처리 방식은 확인되지 않아 별도로 명시하지 않습니다.
**원본 데이터와 DB 백업은 공개 저장소에 포함하지 않으며, 서비스는 별도로 준비한 DB를 조회합니다.**

## 주요 기능과 현재 상태

| 기능 | 상태 |
|---|---|
| 3사 날짜별 매출·증감률·평균 대비 편차 조회 | PostgreSQL 실제 조회 검증 완료. Slack 연결은 후속 작업 |
| 매출 급등·급감 판정 및 관련 콘텐츠 알림 | 원래 임계값 유지. 날짜를 지정한 명시적 실행 |
| 뉴스·유튜브 조회 및 더보기 | 기존 DB 조회와 버튼 동작 보존 |
| 행사·증정 상품 수집 | 브랜드별 수집기와 예약 실행 분리 |
| Tableau 링크 제공 | URL 환경변수 사용. 자동 데이터 갱신 방식은 미확인 |
| 선택적 고정 파일 적재 도구 | 로컬 파일이 있는 경우에만 사용. 일반 서비스 실행에 불필요 |
| 예측 | 과거 시연 후 성능 문제로 제외. `archive/prediction/`에 참고 코드 보존 |
| 회원가입·예시 홈 화면 | 핵심 서비스 연결 미확인. `archive/web_prototype/`에 보존 |

**Aiven PostgreSQL 연결과 로컬 MariaDB 데이터 이전을 완료했습니다.**
원본 DB를 보존했고, 원본·대상의 모든 행 값과 애플리케이션 조회를 검증했습니다.
애플리케이션 서버·새 Slack 앱·Tableau 재연결은 후속 작업입니다.
기존 팀원의 서버 주소·토큰·채널 ID는 새 코드에 포함하지 않습니다.

## 구조

```text
cv_store/
  config/                 환경변수·프로젝트 기준 경로
  collectors/             CU·GS25·Seven 행사와 증정 상품 수집
  database/               연결·파라미터 기반 조회
  ingestion/              고정 파일 전체 검증·적재
  analysis/               기존 매출 편차 임계값 판정
  integrations/slack/     앱·멘션·메시지·알림
  jobs/                   명시적 수집·예약 실행·날짜별 알림
  web/                    선택적 기존 매출 JSON API
data/                     안내문만 공개. 원본·가공 데이터는 로컬 보관, Git 제외
database/schema/          데이터 행 없는 PostgreSQL 스키마 SQL
archive/                  과거 소스·시뮬레이션·예측·실험·웹 시제품
docs/                     분석·파일 대응표·데이터·운영 설명
tests/                    외부 연결 없이 실행하는 회귀 검증
```

## 데이터 흐름

```text
행사 페이지 ── 브랜드별 수집 ──→ event_img / event_plus

로컬 DB의 all_sale / news_search / ytb_video
  ├─→ 날짜·브랜드별 Slack 조회
  └─→ 매출 편차 판정 → Slack 알림 + 관련 링크

Slack '대시보드' / '티피' → 설정된 Tableau URL
```

현재 `all_sale`은 편차·증감률이 저장된 실제 테이블이며, 원본 DB에 트리거나 뷰는 없었습니다.
보존된 로컬 DB의 스키마와 행을 PostgreSQL로 복사했습니다. 지표를 처음 계산했던 과정과
뉴스·영상 최초 적재 경로는 별도 복원 대상입니다. 과거 Excel 적재기의 `sale` 테이블은
실제 DB에 없으므로 기존 매출 DB를 사용할 때 해당 적재기를 실행하지 않습니다.
뉴스·영상은 날짜·브랜드로 연결하며 매출 변동의 인과관계를 확정하지 않습니다.

## 설치와 오프라인 테스트

프로젝트 루트에서 Python 3.10 이상 환경을 사용합니다. 예측용 TensorFlow는 필수가 아닙니다.

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

테스트는 합성 데이터를 사용하며 원본 매출 파일이 없어도 실행됩니다.
실제 DB·Slack·수집 사이트에 연결하지 않습니다.
의존성 버전 범위는 초기 명세이며 운영 환경의 고정 버전은 통합 검증 후 확정합니다.
선택적 파일 적재 도구는 로컬 파일을 별도로 보유한 경우에만 사용합니다.

## 환경 설정과 향후 실행

[.env.example](.env.example)에 필요한 변수명이 있습니다. DB 연결 시 프로젝트 루트의 `.env`를
자동으로 읽으며 이미 지정된 프로세스 환경변수가 우선합니다. 실제 값은 Git에 올리지 마세요.
기본 연결은 PostgreSQL이며 기존 MySQL은 `DB_ENGINE=mysql`로 선택할 수 있습니다.
[Aiven PostgreSQL 연결·점검 절차](docs/postgresql_setup.md)를 참고하세요.

DB 점검 명령은 실행 검증했습니다. Slack·행사 수집·웹 서버 시작은 각각의 환경을 준비한 뒤 사용합니다.

```powershell
# 원본 MariaDB 또는 대상 PostgreSQL 읽기 전용 점검
python -m cv_store.database.inspect source
python -m cv_store.database.inspect target

# 새 Slack 설정으로 조회 봇 실행
python -m cv_store.integrations.slack.app

# 날짜 1회 검사 및 실제 Slack 알림 전송. 재실행하면 중복 알림 가능.
python -m cv_store.jobs.anomaly_alerts --date 2024-10-02

# 행사 1회 수집 및 DB 저장. cu / gs25 / seven / promotions
python -m cv_store.jobs.collect_events cu
# --daily 지정 시 기존 시각으로 예약 실행. 호스트 현지 시간 기준.
python -m cv_store.jobs.collect_events cu --daily

# 선택적 매출 JSON API. 로컬 주소, debug 비활성화.
python -m cv_store.web.app
```

알림 날짜의 자동 진행과 데이터 재생 방식은 추후 설계합니다. 전체 데이터를 미리 적재한 뒤
조회 기준 날짜를 조절하는 방향이며, 봇 시작 시 과거 알림을 자동 전송하지 않습니다.
클라우드 서비스·서버·Slack 워크스페이스/앱 생성·Tableau 게시 기능은 포함하지 않습니다.

이미 DB에 데이터가 보존되어 있다면 파일을 다시 적재할 필요가 없습니다.
`cv_store/database/`가 DB 연결·조회 코드이며 `DB_*` 환경변수로 연결합니다.
과거 원본을 검증·복원해야 할 때만 `python -m cv_store.ingestion.sales --source <Excel경로>`
또는 `python -m cv_store.ingestion.search_trends --source <CSV경로>`를 사용합니다.
기본은 미리보기이며 `--write`를 추가해야 기존 테이블에 실제 쓰기를 수행합니다.

## 상세 문서

- [기존 구조 분석과 파일 대응표](docs/reorganization.md)
- [데이터 파일과 DB 계약](docs/data_dictionary.md)
- [운영 준비 및 미확인 사항](docs/operations.md)
- [Aiven PostgreSQL 연결과 원본 DB 점검](docs/postgresql_setup.md)
- [편의점 전용 Slack 워크스페이스·앱 설정](docs/slack_setup.md)
- [파일 이동·해시 기록](docs/file_manifest.json)
- [과거 구현 보관 정책](archive/README.md)
