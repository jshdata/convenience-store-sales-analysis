# Aiven PostgreSQL 연결과 원본 점검

## 현재 상태

Aiven PostgreSQL 18.6의 기본 DB `defaultdb`로 로컬 `crawling`의 테이블을 이전했습니다.
모든 테이블에서 원본/대상 행별 해시 멀티셋이 일치했고, 별도 연결로 행 수와 실제 조회를 다시 확인했습니다.
원본 MariaDB는 변경하지 않았습니다. SSL 인증서·호스트 검증을 적용합니다.
테이블별 검증 결과와 원본 압축 백업은 Git 제외 대상인 `runtime/migration/backup_*/`에 보관합니다.
원본 데이터나 접속 정보를 문서·스키마 SQL에 포함하지 않습니다.

[postgresql.sql](../database/schema/postgresql.sql)은 데이터 행 없이 새 빈 DB의 테이블을 재현하는 스키마입니다.
이미 이전된 DB에 다시 실행하지 않습니다. 파일 적재가 아니라 기존 DB 조회가 기본 실행 경로입니다.

사용자가 Aiven PostgreSQL 서비스를 생성했습니다. 원본 MariaDB는 보존하며
점검·복사는 원본에 대한 읽기 전용 트랜잭션으로 수행합니다.

## 로컬 설정

프로젝트 루트 `.env`에 `.env.example`의 변수를 설정합니다. DB 연결 시 자동으로 읽으며
프로세스 환경변수가 우선합니다. `.env`·CA 인증서·점검 결과는 Git에 포함하지 않습니다.

- `DB_ENGINE=postgresql`
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`: 새 Aiven 서비스의 Connection information
- `DB_NAME`: 서비스에 실제로 존재하는 DB. 처음에는 기본 `defaultdb`를 사용할 수 있음
- `DB_SSLMODE=verify-full`
- `DB_SSLROOTCERT=runtime/certs/aiven-ca.pem`: 서비스에서 내려받은 Aiven 프로젝트 CA 인증서
- `SOURCE_DB_HOST`, `SOURCE_DB_PORT`, `SOURCE_DB_USER`, `SOURCE_DB_PASSWORD`, `SOURCE_DB_NAME`: 원본 로컬 MariaDB

원본 접속 계정과 대상 Aiven 접속 계정은 별도입니다. 호스트·포트·비밀번호를 혼용하지 않습니다.
CA 파일은 인증서 내용만 있어야 하며 SQL/JSON이나 인증서의 다운로드 URL을 넣으면 안 됩니다.

[Aiven TLS 안내](https://aiven.io/docs/platform/concepts/tls-ssl-certificates)에 따라
`verify-full`로 서버 인증서와 호스트 이름을 검증합니다. 인증서가 없다고 검증을 끄지 않습니다.

## 의존성

```powershell
python -m venv --system-site-packages .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PostgreSQL 드라이버는 pg8000, 원본 MariaDB 조회에는 PyMySQL을 사용합니다.
pg8000은 Python SSLContext로 CA·호스트를 검증하며 Windows libpq의 경로·IPv6 SAN 호환 문제를 피합니다.
기존 MySQL 연결은 `DB_ENGINE=mysql`로 선택할 수 있습니다.

## 쓰기 없는 점검

```powershell
.venv\Scripts\python.exe -m cv_store.database.inspect source
.venv\Scripts\python.exe -m cv_store.database.inspect target
```

- `source`: 테이블·컬럼·인덱스·트리거·뷰와 행 수를 `runtime/migration/source_schema.json`에 저장
- `target`: DB 이름·버전·SSL 연결 여부·public 스키마의 테이블 이름만 확인
- 접속 비밀번호와 실제 데이터 행은 출력하지 않음
- 원본 테이블 생성/변경/삭제·데이터 수정 없음

## 실제 이전 전에 확인할 사항

1. `all_sale`의 실제 25열 이름·자료형과 생성 컬럼·트리거·뷰 여부.
2. `growth_deviation`과 증감률 계산 로직이 저장 데이터인지 DB 객체인지.
3. 관련 테이블 범위와 날짜·브랜드 값. 다른 프로젝트 자료는 임의 이전하지 않음.
4. PostgreSQL용 자료형·자동 증가 키·인덱스·계산 로직 변환.
5. 새 대상 테이블에 복사하고 테이블별 행 수·키·합계·NULL 수를 원본과 대조.

기존 MySQL SQL 덤프를 PostgreSQL에 그대로 실행하지 않습니다.
실제 스키마를 읽어 변환하며 확인되지 않은 원본 행이나 계산식을 추정하여 생성하지 않습니다.

## 실제 스키마에서 확인한 사항

- `all_sale`은 계산 컬럼을 포함한 25열의 실제 테이블이며 생성 컬럼·트리거·뷰가 아닙니다.
- 로컬 `crawling` DB에는 테이블 9개가 있으며 역할이 불명확한 테이블도 삭제하지 않고 보존합니다.
- 검색 트렌드 날짜는 `trend_date`입니다. 과거 코드의 `DATE` 가정은 수정했습니다.
- 과거 Excel 적재기의 `sale` 테이블은 원본 DB에 없습니다. 기존 DB를 사용할 때 그 적재기를 실행하지 않습니다.

## 이전 도구

```powershell
# 원본 구조를 읽고 PostgreSQL 자료형으로 변환 가능한지 검증. 쓰기 없음.
.venv\Scripts\python.exe -m cv_store.database.migrate
# 빈 public 스키마에만 복사. 기존 테이블이 있으면 중단.
.venv\Scripts\python.exe -m cv_store.database.migrate --write
```

하나의 대상 트랜잭션에서 테이블 생성·복사·검증을 수행합니다. 대상이 비어 있지 않으면
덮어쓰지 않으므로 이미 이전된 DB에 이 명령을 다시 실행하면 중단됩니다.
테이블별 원본과 대상의 행 수 및 순서와 무관한 SHA-256 행 해시 멀티셋을 대조합니다.
기본키·자동 증가 ID와 기존 인덱스를 유지하고, 날짜·브랜드 조회용 인덱스를 추가합니다.

자료형 변환은 다음 원칙을 사용합니다.

- 식별자는 소문자로 통일하며 `1+1_event_count`처럼 특수문자가 있는 이름은 인용합니다.
- MySQL `DATETIME`은 시간대 변환 없이 PostgreSQL `TIMESTAMP WITHOUT TIME ZONE`으로 복사합니다.
- MySQL `FLOAT`는 읽어온 값을 보존하도록 `DOUBLE PRECISION`으로 승격합니다.
- unsigned BIGINT는 범위를 보존하는 `NUMERIC(20, 0)`으로 변환합니다.
- CHAR는 원본에서 조회되는 문자열을 보존하도록 같은 길이의 VARCHAR로 변환합니다.
- 원본 문자열·NULL·빈 문자열·날짜·정수 값은 변경하지 않습니다.

원본 스키마·압축 행 백업·검증 결과는 `runtime/migration/backup_*/`에만 저장하며
Git에 올리지 않습니다. 트리거·뷰·외래 키·미지원 자료형이 있으면 자동 이전하지 않습니다.
