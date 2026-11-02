# 편의점 프로젝트 전용 Slack 설정

WAHIS와 별도 워크스페이스·앱·채널·토큰을 사용합니다. 기존 WAHIS 설정은 변경하지 않습니다.
워크스페이스 생성과 앱 설치·토큰 발급은 계정 소유자가 Slack 화면에서 진행합니다.
토큰은 로컬 `.env`에만 저장하고 채팅·스크린샷·Git에 포함하지 않습니다.

## 1. 워크스페이스

[Slack 워크스페이스 생성](https://slack.com/get-started#/createnew)에서 생성합니다.
워크스페이스 이름은 `세븐일레븐 매출 전략`, URL 예시는 `cstore-sales-analysis`입니다.
URL은 사용 가능 여부에 따라 달라질 수 있고 GitHub 이름과 동일할 필요는 없습니다.
기존 Slack 로그인 이메일을 사용할 수 있습니다.

처음에는 `cu-sales` 채널만 만들어 연결을 확인해도 됩니다. 전체 기능에는 다음 채널을 권장합니다.

| 채널 예시 | 환경변수 | 용도 |
|---|---|---|
| `cu-sales` | `SLACK_CHANNEL_CU` | CU 날짜별 매출 |
| `gs25-sales` | `SLACK_CHANNEL_GS25` | GS25 날짜별 매출 |
| `seven-sales` | `SLACK_CHANNEL_SEVEN` | Seven 날짜별 매출 |
| `youtube-trends` | `SLACK_CHANNEL_YOUTUBE` | 영상 조회 |
| `news-trends` | `SLACK_CHANNEL_NEWS` | 뉴스 조회 |
| `sales-alerts` | `SLACK_CHANNEL_ALERT` | 이상 변동 알림 |
| `tableau-dashboard` | `SLACK_CHANNEL_TABLEAU` | Tableau 링크 |

Tableau 재연결 전에는 마지막 채널과 URL 설정을 비워도 됩니다. 각 채널에는 봇을 초대해야 합니다.
설정에는 이름 대신 채널 상세 화면에서 복사한 실제 채널 ID를 넣습니다.

## 2. 앱 생성

1. [Slack 앱 관리](https://api.slack.com/apps) → **Create New App → From a manifest**.
2. 새 편의점 워크스페이스 선택. WAHIS가 선택되지 않았는지 확인.
3. JSON 탭에 [slack_manifest.json](../config/slack_manifest.json)의 전체 내용을 붙여넣고 검토 후 생성.
   앱 이름은 `편의점 경쟁 동향 알리미`, manifest의 봇 이름은 `cstore-strategy-bot`입니다.
   `features.bot_user.display_name`은 영문 소문자·숫자·하이픈·밑줄·마침표만 사용합니다.
4. **OAuth & Permissions → Install to Workspace**에서 권한을 검토하고 설치.
5. 발급된 **Bot User OAuth Token**을 `.env`의 `SLACK_BOT_TOKEN`에 저장.
6. **Basic Information → App-Level Tokens → Generate Token and Scopes**에서
   이름 `socket-mode`, 권한 `connections:write`로 App-Level Token 발급.
7. App-Level Token을 `.env`의 `SLACK_APP_TOKEN`에 저장. 봇 토큰과 서로 다릅니다.

manifest는 Socket Mode, `app_mention` 이벤트, 더보기 버튼용 Interactivity를 켭니다.
봇 권한은 멘션 수신 `app_mentions:read`와 채널 응답 `chat:write` 두 개입니다.
일반 채널 기록·다른 사용자 프로필·파일·관리자 권한은 요청하지 않습니다.
`connections:write`는 App-Level Token의 권한이며 Bot Token Scopes에 추가하는 항목이 아닙니다.

## 3. 연결 확인

```powershell
# 오프라인 설정 형식만 확인. 아직 토큰이 없으면 미입력 변수 이름만 출력.
.venv\Scripts\python.exe -m cv_store.integrations.slack.check
# 인증과 Socket Mode 준비만 확인. 채널에 메시지를 보내지 않음.
.venv\Scripts\python.exe -m cv_store.integrations.slack.check --online
# 조회 봇 시작. 과거 알림·시뮬레이션 자동 전송 없음.
.venv\Scripts\python.exe -m cv_store.integrations.slack.app
```

봇을 초대한 `cu-sales`에서 `@cstore-strategy-bot 2024-10-02`로 먼저 확인합니다.
영상·뉴스 채널에서는 `@cstore-strategy-bot CU 2024-10-02`를 사용합니다.
관련 링크가 3개보다 많으면 더보기 버튼을 확인합니다.

이상 알림은 `SLACK_CHANNEL_ALERT`를 입력한 뒤 지정 날짜만 1회 시험합니다.
이 명령은 실제 메시지를 보내므로 알림 시험용 채널에서 실행합니다.

```powershell
.venv\Scripts\python.exe -m cv_store.jobs.anomaly_alerts --date 2024-10-02
```

## 확인 범위

로컬 설정 검사는 토큰 유효성이나 봇의 채널 참가를 확인하지 않습니다.
온라인 검사도 두 토큰이 동일한 앱에서 발급됐는지, 모든 채널에 봇이 초대됐는지를 보장하지 않습니다.
앱 설정 화면과 채널별 실제 멘션 응답으로 최종 확인합니다.
Socket Mode이므로 로컬 시험에 공개 HTTP 서버나 Request URL은 필요하지 않습니다.

## 공식 문서

- [워크스페이스 생성](https://slack.com/help/articles/206845317-Create-a-Slack-workspace)
- [Socket Mode](https://docs.slack.dev/apis/events-api/using-socket-mode/)
- [앱 manifest](https://docs.slack.dev/reference/app-manifest/)
