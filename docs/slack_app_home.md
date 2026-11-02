# Slack 앱 홈 대시보드

봇의 개인 홈 탭에서 날짜·브랜드를 선택하고 ‘조회 / 새로고침’을 눌러 DB 결과를 갱신합니다.
채널 메시지 전송이나 과거 이상치 알림 재발송은 하지 않습니다.

## 화면

- 기본 기간 2024-11-01~2024-12-31, 기본 브랜드 세븐일레븐.
- 시작일·종료일, 브랜드, 그래프 종류(3쌍 증감률 비교 / 선택 브랜드 평균 대비 편차) 선택.
- 선택 브랜드의 기간 매출, 3사 내 매출 비중, 이상치 건수, 최근일 편차.
- 선택 기간의 PNG 그래프와 2024년 고정 5·95백분위 실선.
- 선택 브랜드의 최근 이상치 최대 5건. 이 목록과 알림은 기존 브랜드−3사 평균 기준.
- 최근 이상치 날짜(없으면 최근 매출일)의 뉴스·영상 각각 최대 3건.
- 같은 조회 조건으로 Streamlit을 여는 버튼.

쌍별 그래프의 5·95백분위는 새 비교 지표이며 과거 프로젝트의 원래 방식으로
검증된 것은 아닙니다. 전체 시장점유율이나 뉴스의 인과관계로 해석하지 않습니다.
입력 변경 후 ‘조회’를 눌러야 반영되며 자동 주기 갱신은 하지 않습니다.
Render 무료 서비스가 휴면이면 먼저 서비스 URL을 열어 깨워야 합니다.

## Slack 앱 설정

기존 앱을 사용하며 새 앱이나 토큰을 만들지 않습니다.

1. Slack 앱 관리 → 기존 앱 → App Home → Home Tab 활성화.
2. Event Subscriptions → Subscribe to bot events → `app_home_opened` 추가 → Save Changes.
3. 기존 `app_mention`과 Socket Mode·Interactivity 설정 유지.
4. Slack에서 앱을 열고 ‘홈’ 탭을 선택.

같은 내용은 `config/slack_manifest.json`에 반영되어 있습니다.
기존 `app_mentions:read`, `chat:write` 권한을 유지하며 파일 업로드 권한은 추가하지 않습니다.
`views.publish`로 개인 홈을 게시하며 API에 추가 OAuth scope는 필요하지 않습니다.

## Render 설정과 이미지 처리

`SLACK_PUBLIC_BASE_URL`에 `https://cstore-strategy-demo.onrender.com`과 같은
기존 Render 서비스의 HTTPS 기본 주소를 지정합니다. `DASHBOARD_URL`은 별도의 Streamlit 주소입니다.

홈 조회 시 DB에서 집계를 읽어 PNG를 생성하고 메모리에 저장합니다.
`/slack/home-chart/<임의 토큰>.png`는 해당 이미지 바이트만 반환하며 DB를 조회하지 않습니다.
이 주소는 Slack 이미지 프록시가 가져갈 수 있는 임시 접근 URL이므로 공유하거나 로그로 출력하지 않습니다.

- 접근 토큰은 무작위 192비트이며 이미지별로 새로 생성.
- 저장소는 최대 32개, 유효기간 30분. 개수 초과·만료·서버 재시작 시 접근 불가.
- 별도 디스크·스토리지·이미지 호스팅 서비스를 생성하지 않음.
- 인증 정보나 원자료 파일을 URL에 넣지 않음. PNG는 선택 기간의 집계 그래프만 포함.
- Slack 자체의 이미지 캐시 보존 기간은 이 임시 저장소의 만료와 별개.
- 오래된 화면의 이미지가 없으면 홈을 다시 열거나 조회 버튼으로 갱신.

렌더링은 `matplotlib`의 비대화형 Agg 백엔드로 수행하며 외부 차트 서비스에 데이터를 보내지 않습니다.
기존 Streamlit·Slack 수치는 읽기 전용으로 재사용하며 원본 DB는 수정하지 않습니다.

## 검증

합성 자료로 날짜 범위 검증, 기존 임계값 경계, 쌍별 차이, 즉시 ack,
이미지 만료·개수 제한·조회 경로, 홈 블록 구성과 PNG 출력을 확인합니다.
실제 DB의 2024-11~12 기간으로 Streamlit과 쌍별 기준값이 일치하는지도 확인했습니다.
Slack 홈 활성화·이벤트 구독·실제 화면 게시와 조작은 배포 후 별도로 확인합니다.

- [App Home](https://docs.slack.dev/surfaces/app-home/)
- [views.publish](https://docs.slack.dev/reference/methods/views.publish/)
- [Image block](https://docs.slack.dev/reference/block-kit/blocks/image-block/)
