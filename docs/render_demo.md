# Render 무료 시연용 배포

## 운영 범위

현재 Socket Mode 봇을 **무료 시연용 웹 서비스**로 실행합니다. 24시간 운영을 보장하지 않습니다.
서버를 깨우기 위해 시연 전에 서비스 URL을 열고 `slack_connected: true`를 확인합니다.
매출·뉴스·영상은 Slack에서만 응답하며 공개 HTTP 경로에 데이터 조회 API를 연결하지 않습니다.

- 무료 웹 서비스는 15분간 외부 요청이 없으면 중지될 수 있습니다.
- 중지된 상태에서 Slack 멘션은 현재 Socket Mode 서버를 깨우지 못합니다.
- 자동 이상치 반복 발송/스케줄러는 이 배포에서 실행하지 않습니다.
- 중지·재배포·재시작 시 로컬 파일은 사라집니다. 데이터는 기존 Aiven DB에 보존합니다.
- 무료 실행 시간은 워크스페이스별 월 750시간을 모든 무료 서비스가 공유합니다.
- WAHIS에 영향을 주지 않도록 전용 **Hobby 워크스페이스**에 새 서비스를 생성합니다.
- 자동 keep-alive 요청으로 유휴 중지를 우회하지 않습니다.
- 무료 시간·빌드·트래픽 한도와 결제수단/사용량 지출 제한을 콘솔에서 확인합니다.
  Free compute 선택만으로 모든 초과 사용료가 자동 차단되는 것은 아닙니다.

## 서비스 구성

| 항목 | 값 |
|---|---|
| 서비스 이름 | `cstore-strategy-demo` |
| 서비스 종류/요금제 | Web Service / **Free** |
| 저장소 | `jshdata/convenience-store-sales-analysis`, `main` |
| Python | `.python-version`의 3.12 최신 패치 |
| Build Command | `pip install -r requirements/render-demo.txt` |
| Start Command | `gunicorn 'cv_store.integrations.slack.web:create_app()' --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120` |
| Region | Singapore (기존 Aiven은 유지) |
| DB | 기존 Aiven PostgreSQL. Render DB를 새로 만들지 않음 |

Gunicorn worker는 **1개만** 사용합니다. worker를 늘리면 Socket Mode 연결이 중복 생성됩니다.
초기 설정 중에는 TCP 상태 확인으로 웹 서버를 확인할 수 있지만, 서비스가 live라고 해서
봇 연결까지 성공한 것은 아닙니다. `/health`와 실제 Slack 멘션으로 확인해야 합니다.
설정이 없으면 공개 `/`는 `configuration_required`, `/health`는 503을 반환하고 봇은 연결하지 않습니다.

## 환경변수와 인증서

서버에는 DB/Slack 및 필요한 채널 설정만 입력합니다. `SOURCE_DB_*`는 로컬 이전용이므로 올리지 않습니다.
공통 WAHIS 환경변수 그룹을 연결하지 않습니다.

`DB_ENGINE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`DB_SSLMODE=verify-full`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_*`.
Tableau URL은 준비된 경우에만 입력합니다.

Render Secret Files에 파일명 `aiven-ca.pem`으로 기존 CA 인증서를 추가하고
`DB_SSLROOTCERT=/etc/secrets/aiven-ca.pem`을 설정합니다.
CA 파일은 로컬 `runtime/certs/aiven-ca.pem`에 있으며 GitHub에는 포함하지 않습니다.
`.env`를 통째로 업로드하지 않고 배포에 필요한 키만 전달합니다.

## 검증과 전환

1. 코드 Commit·Push 후 무료 서비스 생성.
2. 환경변수·Secret File 입력 후 **Deploy**. 설정만 저장했으면 아직 런타임에 반영되지 않을 수 있음.
3. 새 배포가 live인지 확인하고 URL에서 `slack_connected: true` 확인.
4. 기존 로컬 봇을 종료해 테스트 응답이 서버에서 온 것인지 구분.
5. CU/GS25/Seven 조회와 뉴스·영상 더보기 시험.
6. 정상 확인 전에는 로컬 봇을 계속 사용할 수 있음. 실패하면 로컬 실행으로 복구.

자동 배포 활성 여부는 연결 방식에 따라 다릅니다. 공개 Git URL로 연결한 서비스는
수동 배포가 필요할 수 있으므로 실제 서비스 설정을 확인합니다.

## 공식 문서

- [무료 서비스 제한](https://render.com/docs/free)
- [워크스페이스 생성](https://render.com/docs/team-members)
- [환경변수·Secret Files](https://render.com/docs/configure-environment-variables)
- [Python 버전](https://render.com/docs/python-version)
