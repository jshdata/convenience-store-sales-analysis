# Streamlit 매출 전략 대시보드

기존 Tableau 자료를 보존하면서 현재 Aiven PostgreSQL을 조회하는 별도 화면입니다.
로컬 실행과 Community Cloud 배포를 지원합니다.
2026-11-02 Community Cloud 배포와 Render의 `DASHBOARD_URL` 설정을 완료했습니다.
[공개 대시보드](https://convenience-store-sales-analysis-srfzzkpg6ixhfihmvgej6l.streamlit.app/)

## 로컬 실행

프로젝트 루트에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/dashboard.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

브라우저에서 `http://127.0.0.1:8501`을 엽니다.
기존 `.env`의 대상 DB 설정(`DB_*`)과 `DB_SSLROOTCERT` CA 파일을 사용합니다.
`SOURCE_DB_*`나 Slack 토큰은 대시보드 기능에 필요하지 않습니다.
별도 의존성 파일로 관리하므로 Render Slack 서버 빌드에는 추가되지 않습니다.

## 기능과 데이터 흐름

```text
Aiven all_sale → repository.get_dashboard_sales → dashboard.model
                                              → 매출 추이 / 비중 / 편차와 이상치
이상치 날짜·브랜드 → repository.get_dashboard_context → 뉴스·유튜브 링크
```

- 조회 기간과 비교 브랜드, 상세 분석 브랜드를 선택합니다.
- 브랜드 간 증감률 차이 탭에서 CU−GS25, GS25−세븐일레븐, CU−세븐일레븐을 비교합니다.
  값은 같은 날짜 두 브랜드 증감률의 차이(%p)이며 0선 위·아래는 상대적 우위를 뜻합니다.
  두 브랜드 값이 모두 존재하는 날짜만 표시합니다. 각 쌍의 2024년 전체 차이에서
  5·95백분위수를 선형 보간으로 계산해 고정 실선을 그립니다. 조회 기간 필터는
  기준 산출 기간에 영향을 주지 않습니다. 상한 이상은 빨강, 하한 이하는 파랑입니다.
  이 쌍별 기준은 새 비교 지표이며 과거 프로젝트의 원래 계산식으로 확인된 것은 아닙니다.
  기존 Slack 판정은 별도의 3사 평균 대비 이상치 탭과 표에 유지합니다.
- 초기 범위는 2024년 11월 1일~12월 31일이며 보유 기간 안으로 제한합니다.
  이 기간의 데이터가 전혀 없으면 마지막 보유일까지 최대 61일을 표시합니다. 오늘의 실시간 매출이 아닙니다.
- 매출 비중은 선택 기간의 전체 3사 합계를 분모로 사용합니다.
  비교 브랜드를 일부만 선택해도 분모는 유지합니다. 전체 시장점유율이 아닙니다.
- [고정 5·95백분위 기준](anomaly_method.md)을 사용하며 기간 필터로 경계선을 재계산하지 않습니다.
  첫날 결측 지표는 미산출입니다.
- 뉴스·영상은 같은 날짜·브랜드로 각 최대 10건의 원문 링크를 보여줍니다.
  인과관계를 추정하지 않으며 자동 크롤링하거나 영상을 재생하지 않습니다.
- 조회 결과는 5분 캐시합니다. 화면에 DB 조회 시각을 표시하고 새로고침으로 다시 조회합니다.
- DB 조회만 수행합니다. Slack 발송·스케줄·데이터 적재·자동 시뮬레이션은 실행하지 않습니다.

## 외부 배포 전 후속 작업

1. 로컬 화면·필터·수치 검토.
2. 공개할 데이터 범위와 접근 대상을 정하고 필요하면 읽기 전용 DB 계정 구성.
3. 아래 Community Cloud 설정으로 배포하고 연결 확인.
4. 배포 URL 검증 후 Slack 대시보드 링크 기능을 전환.

비밀번호·원본 데이터·Tableau 추출 파일은 커밋하지 않습니다.
무료 서비스의 휴면·리소스 한도는 실제 배포 시 공식 문서에서 다시 확인합니다.

## Streamlit Community Cloud 설정

| 항목 | 값 |
|---|---|
| Repository | `jshdata/convenience-store-sales-analysis` |
| Branch | `main` |
| Main file path | `dashboard/streamlit_app.py` |
| Python | 3.12 |
| App URL 후보 | `cstore-sales-strategy.streamlit.app` (사용 가능 여부에 따라 변경) |

별도 진입점 폴더의 `dashboard/requirements.txt`가 대시보드 전용 의존성을 불러옵니다.
기존 Render Slack 서버의 빌드 명령과 요금제는 변경하지 않습니다.

Advanced settings의 Secrets에 DB 설정을 TOML 형식으로 입력합니다.
로컬 `.streamlit/secrets.toml`은 Git 제외 대상이며, 배포용 파일은
`runtime/deploy/streamlit-secrets.toml`로 준비할 수 있습니다. 파일 내용은 채팅에 붙이지 않습니다.

```toml
DB_ENGINE = "postgresql"
DB_HOST = "<Aiven host>"
DB_PORT = "<port>"
DB_USER = "<user>"
DB_PASSWORD = "<password>"
DB_NAME = "defaultdb"
DB_SSLMODE = "verify-full"
DB_SSLROOTCERT_PEM = """-----BEGIN CERTIFICATE-----
<Aiven CA certificate>
-----END CERTIFICATE-----"""
```

CA 본문으로 SSLContext를 생성하고 호스트명·인증서 검증을 유지합니다.
로컬에서는 기존 CA 파일 경로도 계속 지원하며, PEM 본문이 있으면 우선합니다.
대시보드가 허용하는 DB Secrets만 환경변수에 반영하고 기존 프로세스 설정은 덮어쓰지 않습니다.
대시보드의 공개 여부는 Streamlit 설정에 따르며 코드에 별도 로그인 기능은 없습니다.

## Slack 연결

1. 배포 후 공개 URL이 정상적으로 DB 데이터를 표시하는지 확인합니다.
2. Render Slack 서비스 Environment와 로컬 `.env`에 `DASHBOARD_URL=https://...streamlit.app`을 지정합니다.
3. 코드와 환경변수가 반영된 Render 배포를 확인합니다.
4. 기존 CU·GS25·Seven·뉴스·영상·알림 등 설정된 채널에서 `@봇 대시보드`를 요청합니다.
   브랜드별 매출 채널에서는 해당 브랜드가 선택된 URL을 반환합니다.
5. 이후 생성되는 이상치 알림에는 ‘대시보드에서 확인’ URL 버튼이 추가됩니다.
   `brand`, `event`, `start`, `end` 쿼리로 해당 브랜드·날짜와 전후 14일 범위를 선택합니다.
   링크를 여는 것만으로 알림이 재발송되지는 않습니다.

`DASHBOARD_URL`이 비어 있으면 알림은 기존대로 동작하며 링크 버튼을 추가하지 않습니다.
기존 Tableau 채널·환경변수·`티피` 명령도 보존합니다. 예전 메시지에는 새 버튼이 소급 추가되지 않습니다.

- [공식 배포 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [의존성 파일 탐색 순서](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Secrets 설정](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
