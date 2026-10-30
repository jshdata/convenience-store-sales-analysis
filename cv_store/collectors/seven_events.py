"""seven_schedule.py에서 분리한 수집기. import 시 수집·DB 연결을 실행하지 않습니다."""
from cv_store.config.settings import chrome_driver_path
from cv_store.database.connection import connect_db

import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

def connect_db_with_existing_events():
    """MariaDB 연결 및 기존 저장된 이벤트 데이터 조회"""
    conn = None
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # 기존 저장된 이벤트 제목과 이미지 URL 가져오기 (중복 방지)
        cursor.execute("SELECT event_title, img_url FROM event_img")
        existing_data = {(row[0], row[1]) for row in cursor.fetchall()}  # (title, img_url) 형태로 저장

        return conn, cursor, existing_data
    except Exception as e:
        if conn is not None:
            conn.close()
        print(f"❌ MariaDB 연결 오류: {e}")
        return None, None, set()


def open_event_page():
    """ 세븐일레븐 이벤트 페이지를 새로 엶 (HEADLESS 모드) """
    driver = webdriver.Chrome(service=Service(chrome_driver_path()), options=_chrome_options())
    driver.get("http://m.7-eleven.co.kr/product/eventList.asp")
    time.sleep(3)  # 페이지 로딩 대기
    return driver


def scrape_events(driver, existing_data):
    """ 현재 페이지의 이벤트를 크롤링 """
    wait = WebDriverWait(driver, 10)  # 최대 10초까지 대기
    event_details = []  # 새로운 데이터 저장 리스트

    try:
        # ✅ 이벤트 목록이 로드될 때까지 대기
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#listUl li a")))

        # ✅ 이벤트 목록 가져오기 (매번 새로 가져옴)
        events = driver.find_elements(By.CSS_SELECTOR, "#listUl li a")
        print(f"🔍 총 {len(events)}개의 이벤트 발견!")

        for index in range(len(events)):
            try:
                # 상세 페이지 왕복 후에는 이전 WebElement를 재사용하지 않습니다.
                event = driver.find_elements(By.CSS_SELECTOR, "#listUl li a")[index]
                # ✅ 이벤트 ID 추출 (fncGoView(1143) 형태에서 1143 추출)
                event_id_match = re.search(r"fncGoView\((\d+)\)", event.get_attribute("href"))
                if not event_id_match:
                    continue
                event_id = event_id_match.group(1)

                # ✅ 이벤트 제목 가져오기
                title_element = event.find_element(By.TAG_NAME, "strong")
                title = title_element.text.strip()

                # ✅ 이벤트 기간 (YYYY-MM-DD ~ YYYY-MM-DD)
                date_element = event.find_element(By.TAG_NAME, "span")
                date_range = date_element.text.strip()
                start_date, end_date = date_range.split(" ~ ")

                # ✅ 이벤트 상세 페이지 이동
                driver.execute_script("arguments[0].click();", event)
                time.sleep(2)  # 상세 페이지 로딩 대기
                
                # ✅ 상세 페이지에서 이미지 URL 가져오기
                img_url = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".event_wrap_view img"))).get_attribute("src")
                convenience_store = "seven"  # ✅ "세븐일레븐"

                # ✅ **중복 체크 (event_title + img_url)**
                if (title, img_url) in existing_data:
                    print(f"⚠️ 중복 이벤트 무시: {title} (이미 존재하는 이미지 URL 포함)")
                    driver.back()
                    time.sleep(2)  # 로딩 대기
                    continue

                # ✅ 새로운 데이터 저장
                event_details.append((img_url, start_date, end_date, title, convenience_store))
                existing_data.add((title, img_url))  # 저장된 데이터 Set에 추가

                # ✅ 실시간 진행 상황 출력
                print(f"[{len(event_details)}] 저장: {title}, {start_date}, {end_date}, {img_url}, {convenience_store}")

                # ✅ 상세 페이지에서 돌아가기
                driver.back()
                time.sleep(2)  # 로딩 대기

                # ✅ 요소 갱신 (stale element 방지)
                events = driver.find_elements(By.CSS_SELECTOR, "#listUl li a")

            except Exception as e:
                print(f"❌ 데이터 수집 오류: {e}")
                continue

    except Exception as e:
        print(f"❌ 크롤링 중 오류 발생: {e}")

    return event_details


def save_data_to_db(conn, cursor, event_details):
    """ MariaDB에 크롤링 데이터를 저장 """
    insert_sql = """
    INSERT INTO event_img (img_url, start_date, end_date, event_title, store_type, idx)
    VALUES (%s, %s, %s, %s, %s, 0)  -- idx 값을 항상 0으로 고정
    """

    if event_details:
        try:
            cursor.executemany(insert_sql, event_details)
            conn.commit()
            print(f"✅ {len(event_details)}개의 새로운 이벤트가 DB에 저장되었습니다!")
        except Exception as e:
            conn.rollback()
            print(f"❌ DB 저장 오류: {e}")
    else:
        print("⚠️ 새로운 데이터가 없어 DB 업데이트하지 않았습니다.")


def run_crawling():
    """ 크롤링 실행 함수 (스케줄러에서 호출) """
    print(f"\n🕛 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 자동 크롤링 시작...")
    
    # **DB 연결**
    conn, cursor, existing_data = connect_db_with_existing_events()
    if conn is None or cursor is None:
        print("❌ DB 연결 실패로 인해 크롤링을 중단합니다.")
        return

    # **크롤링 실행**
    driver = None
    try:
        driver = open_event_page()
        event_details = scrape_events(driver, existing_data)
        save_data_to_db(conn, cursor, event_details)
    finally:
        cursor.close()
        conn.close()
        if driver is not None:
            driver.quit()

    print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 크롤링 완료!\n")


def _chrome_options():
    options = webdriver.ChromeOptions()
    for flag in ("--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"):
        options.add_argument(flag)
    return options

if __name__ == "__main__":
    run_crawling()
