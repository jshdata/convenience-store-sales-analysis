# 데이터 출처와 DB 연동

## 매출 데이터 출처

프로젝트 수행 당시 멘토를 통해 제공받은 약 1년 분량의 비식별 카드 결제 기반
편의점 매출 집계 데이터를 활용했습니다. 일자·브랜드별 총매출과 성별·연령대별 매출을
분석하여 매출 변동 및 이상 구간을 확인했습니다.

원천 제공기관·카드사·구체적인 비식별 처리 방식은 확인되지 않아 추정하여 명시하지 않습니다.
비식별 데이터라는 설명이 공개·재배포 권한을 뜻하지는 않으므로 원본과 DB 백업은 공개하지 않습니다.
개별 결제 내역을 공개하는 저장소가 아니라 분석 코드와 연동 구조를 설명하는 저장소입니다.

기존 파일에는 매출 Excel(`all.xlsx`, `sale_gender_age.xlsx`)과 영상·검색 트렌드 등의 CSV가
함께 있었습니다. 파일은 로컬에 보존하지만 Git 업로드에서 제외합니다.

## DB를 사용하는 실행 방식

보존된 로컬 MariaDB의 9개 테이블을 Aiven PostgreSQL로 이전하고 모든 행 값의 일치를 검증했습니다.
현재 서비스는 Aiven DB를 조회하며 매번 Excel·CSV를 적재할 필요가 없습니다.
`cv_store/database/connection.py`와 `repository.py`가 이미 연결·조회 책임을 담당합니다.
DB 접속은 `DB_*` 환경변수와 CA 인증서로 설정합니다. 인증 정보와 원본 행은 공개하지 않습니다.

보존된 매출 범위는 **2024-01-01~2025-02-06, 403일 × 3개 브랜드 = 1,209행**입니다.
프로젝트 당시 약 1년 분량을 제공받았다는 설명과 현재 DB의 보존 범위는 구분합니다.
현재 스키마는 [PostgreSQL DDL](../database/schema/postgresql.sql)에 공개하고 있습니다.

## 데이터 목록과 확인 수준

아래는 이전한 9개 원본 테이블과 이후 생성한 시뮬레이션 테이블의 구분입니다.
현재 조회 기능의 연결 여부와 과거 데이터의 보존 가치는 별개입니다.

| 테이블 | 데이터 성격·출처 근거 | 주요 열 | 현재 활용·확인할 점 |
|---|---|---|---|
| `all_sale` | 멘토를 통해 제공받은 비식별 카드 기반 매출 집계와 분석용 가공 열 | `sale_date`, `store_type`, `sum_amount`, `store_count`, 성별·연령대별 매출, 증감률·편차 | 핵심 분석·알림·시뮬레이션에 사용. 원천 기관·최초 가공 과정은 미확인 |
| `news_search` | 기존 네이버 기사 검색 기능과 보존된 기사 데이터 | `news_title`, `news_url`, `news_summary`, `news_date`, `news_agency`, `store_type` | 날짜·브랜드별 기사 연결. 최초 API·검색 조건·수집 주기는 미확인 |
| `ytb_video` | 기존 YouTube 조회 기능과 보존된 영상 데이터 | `video_id`, `video_title`, `published_at`, `video_url`, `channel_id`, `store_type` | 날짜·브랜드별 영상 연결. 조회 수 등은 보존된 값이며 실시간 값이 아님 |
| `ytb_channel` | 보존된 YouTube 채널 데이터 | `channel_id`, `channel_title`, `channel_view_count`, `subscriber_count`, `video_count` | 현재 핵심 조회에는 직접 사용하지 않음. 원래 적재 과정 추가 확인 필요 |
| `event_img` | 공식 행사 페이지 수집 코드 보존 | `event_title`, `img_url`, `start_date`, `end_date`, `store_type` | 행사 자료 보존. 현재 핵심 조회 화면에는 미연결 |
| `event_plus` | Pyony 브랜드별 상품 수집 코드 보존 | `plus_title`, `plus_price`, `plus_event_price`, `plus_type`, `update_date`, `store_type` | 증정·행사 상품 자료 보존. 사이트 변경에 따른 재검증 필요 |
| `naver_search_trend` | 기존 검색 트렌드 자료·파일 적재 코드 보존 | `trend_date`, `seven`, `gs25`, `cu`, `cs` | 현재 핵심 서비스에는 미연결. 검색어·정규화 기준·수집 조건 미확인 |
| `people` | 원본 DB에 있던 보조 테이블. 원천 출처 미확인 | `region`, `people`, `man`, `woman`, 브랜드별 열, `cleanaddr`, `x`, `y`, `sale_date` | 열 이름으로 지역·인구·좌표 정보를 확인. 단위·결합 키·브랜드별 열 의미는 추가 확인 |
| `hospital_sale` | 원본 DB에 있던 보존 테이블. 원천 출처 미확인 | `store_type`, `sale`, `store_count`, `sale_date` | 핵심 서비스에는 미연결. 이름만으로 업종이나 매출 단위를 확정하지 않음 |
| `simulation.runs` | 현재 서비스가 생성하는 운영 상태 | 실행 ID, 소유자, 기간·대상·임계값, 다음 날짜·진행 상태 | 원본 매출과 분리. 사용자가 새 실행을 만들 때 저장 |
| `simulation.events` | 현재 서비스가 생성하는 발송 이력 | 실행 ID, 날짜·브랜드, 편차·금액, 발송 상태·Slack 메시지 식별자 | 동일 실행의 중복 발송 방지와 결과 확인. 외부 수집 데이터가 아님 |

이 목록은 데이터 원본을 공개하지 않고 구조·출처·활용 범위만 설명합니다.
시뮬레이션 상태의 실제 소유자·메시지 식별자 등 운영 값도 공개하지 않습니다.

## 코드가 기대하는 최소 DB 계약

원본 행은 공개하지 않더라도 아래 열 설명은 코드 이해와 새 DB 연결을 위해 유지합니다.
로컬 DB 점검과 PostgreSQL 이전에서 사용하는 열을 확인했습니다.

| 이름 | 사용하는 데이터 |
|---|---|
| `all_sale` | `sale_date`, `store_type`, `sum_amount`, `sum_amount_growth`, `avg_sum_amount_growth`, `growth_deviation` |
| `all_sale`의 선택적 웹 API 열 | `id_sale`, `store_count`, `man10`~`man60`, `woman10`~`woman60`, `day`, `kind_day` |
| `ytb_video` | `video_url`, `store_type`, `published_at` |
| `news_search` | `news_url`, `store_type`, `news_date` |
| `event_img` | `idx`, `img_url`, `start_date`, `end_date`, `event_title`, `store_type` |
| `event_plus` | `store_type`, `update_date`, `plus_title`, `plus_price`, `plus_event_price`, `plus_type` |
| `naver_search_trend` | PostgreSQL의 `trend_date`, `seven`, `gs25`, `cu`, `cs` (이전 원본의 `DATE`, `GS25`, `CU`를 변환) |

기존 코드가 사용하는 브랜드 값은 `CU`, `GS25`, `seven`입니다.
이전 시 원본 브랜드 값은 보존하고 조회에서는 대소문자를 정규화합니다.
역할이 불명확한 테이블도 원본 보존을 위해 복사했지만 임의로 핵심 서비스에 연결하지는 않습니다.

## 뉴스·영상·행사 출처

- 행사·증정 상품: 기존 코드에 CU·GS25·세븐일레븐 공식 행사 페이지와 Pyony 수집 경로가 있습니다.
- 뉴스: 기존 서비스에서 네이버 기사 조회 기능을 제공했으며 현재 코드는 보존된 `news_search`를 조회합니다.
- 영상·채널: 기존 서비스에서 YouTube 정보를 활용했으며 현재 코드는 보존된 `ytb_video`를 조회합니다.
- 검색 트렌드: 네이버 검색 트렌드 자료로 사용된 파일이 남아 있으나 원래 수집 과정·조건은 추가 확인이 필요합니다.

뉴스·영상 최초 수집 및 적재 코드가 모두 남아 있는 것은 아니므로 수집 API·쿼터·갱신 주기를 추정하지 않습니다.
Tableau 링크 제공은 확인되었지만 DB 새로고침 방식은 별도 확인 대상입니다.

## 선택적 파일 적재 도구

`cv_store/ingestion/`은 기존 파일을 검증·복구할 필요가 있을 때만 사용합니다.
`all.xlsx`와 트렌드 CSV는 헤더 없이 읽고 첫 행을 보존합니다.
매출 적재기는 과거 코드의 `sale`을 대상으로 하며 `all_sale`을 자동 생성하지 않습니다.
실제 로컬 DB에 `sale`은 없으므로 기존 DB를 사용하는 동안 그 과거 적재기를 실행하지 않습니다.

전체 매출·검색 트렌드 파일과 이전 체크포인트는 Git 제외 대상입니다.
공개 테스트는 합성 자료를 사용하므로 이 파일이 없어도 실행됩니다.

## 이상 판정

임계값은 기존 코드 그대로 유지합니다.
CU는 1.252 이상 / -1.344 이하, GS25는 1.135 이상 / -1.461 이하,
seven은 1.394 이상 / -1.374 이하를 각각 급등 / 급감으로 판정합니다.
`growth_deviation`은 브랜드별 전날 대비 매출 증감률에서 같은 날 3사 증감률의
산술평균을 뺀 값이며 단위는 %p입니다. 현재 채택한 알림 기준은 2024년 전체
브랜드별 편차의 5·95백분위수입니다. 재계산한 값을 소수 셋째 자리로 반올림하면
기존 임계값 6개와 모두 일치합니다. 검증 근거와 한계는 [이상치 판정 방법](anomaly_method.md)을 참고합니다.
관련 뉴스·영상은 날짜·브랜드 기준으로 연결하며 매출 변동의 인과관계를 확정하지 않습니다.
