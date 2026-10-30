"""CU_schedule.py에서 분리한 수집기. import 시 수집·DB 연결을 실행하지 않습니다."""
from cv_store.database.connection import connect_db

import requests
from bs4 import BeautifulSoup
import datetime
import calendar

def run_script():
    conn = connect_db()
    try:
        _collect_events(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _collect_events(conn):
    # 1. DB 연결
    cursor = conn.cursor()

    # 2. DB에서 가장 최근 idx 가져오기 (기본값 없이 사용)
    cursor.execute("SELECT MAX(idx) FROM event_img WHERE store_type = %s", ("CU",))
    latest_idx = cursor.fetchone()[0]  # 가장 최근 idx (None일 수도 있음)

    # 데이터가 아예 없으면 크롤링 중지
    if latest_idx is None:
        print("DB에 기존 데이터가 없습니다. 크롤링을 시작할 수 없습니다.")
        cursor.close()
        return

    print(f"DB에서 가장 최근 idx: {latest_idx}")

    # 3. 크롤링할 URL 설정
    base_url = "https://cu.bgfretail.com/brand_info/news_view.do?category=brand_info&depth2=5&idx="

    # 4. 오늘 날짜 및 해당 월의 마지막 날짜 계산
    today = datetime.date.today()
    start_date = today.strftime("%Y-%m-%d")
    last_day_of_month = calendar.monthrange(today.year, today.month)[1]
    end_date = today.replace(day=last_day_of_month).strftime("%Y-%m-%d")

    # 5. 새로운 데이터 크롤링
    new_data = []
    idx = latest_idx + 1  # DB에 있는 가장 최신 idx의 다음 값부터 크롤링 시작

    while True:
        url = base_url + str(idx)
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # 이벤트 제목
            event_tag = soup.select_one("thead tr th")
            event_title = event_tag.get_text(strip=True) if event_tag else None

            # 이미지 URL
            img_tag = soup.select_one('td[colspan="2"] img[border="0"]')
            img_url = img_tag["src"] if img_tag else None

            # 편의점 종류 (CU로 고정)
            store_type = "CU"

            # 데이터가 유효한지 체크 (NULL 값일 경우 종료)
            if not event_title or not img_url:
                print("유효하지 않은 데이터 발견. 크롤링 중지.")
                break

            # 새로운 데이터 저장
            new_data.append((idx, img_url, start_date, end_date, event_title, store_type))
            print(f"새로운 데이터 추가: idx {idx}, {event_title}, img_url: {img_url}")

        else:
            print("더 이상 유효한 데이터를 찾을 수 없습니다.")
            break

        idx += 1  # 다음 idx로 이동

    # 6. 새 데이터 DB 저장
    if new_data:
        insert_sql = """
        INSERT INTO event_img (idx, img_url, start_date, end_date, event_title, store_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.executemany(insert_sql, new_data)
        conn.commit()
        print(f"{len(new_data)}개의 새로운 데이터를 삽입했습니다.")

    # 7. 종료
    cursor.close()


if __name__ == "__main__":
    run_script()
