"""GS25_schedule.py에서 분리한 수집기. import 시 수집·DB 연결을 실행하지 않습니다."""
from cv_store.config.settings import chrome_driver_path
from cv_store.database.connection import connect_db

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
base_url = "http://gs25.gsretail.com/gscvs/en/customer-engagement/event/current-events"



def is_event_exists(event_info):
    """이미 저장된 이벤트인지 확인"""
    conn = connect_db()
    cursor = conn.cursor()
    query = """
    SELECT COUNT(*) FROM event_img 
    WHERE img_url = %s AND start_date = %s AND end_date = %s 
          AND event_title = %s AND store_type = %s
    """
    cursor.execute(query, (
        event_info["이미지 주소"],
        event_info["이벤트 시작 날짜"],
        event_info["이벤트 끝 날짜"],
        event_info["이벤트 제목"],
        event_info["편의점"]
    ))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count > 0


def save_to_db(event_info):
    """데이터 저장"""
    if is_event_exists(event_info):
        print(f"⏭ 이미 존재하는 이벤트: {event_info['이벤트 제목']}, 저장 생략")
        return

    conn = connect_db()
    cursor = conn.cursor()
    insert_sql = """
    INSERT INTO event_img (img_url, start_date, end_date, event_title, store_type, idx)
    VALUES (%s, %s, %s, %s, %s, 0)
    """
    cursor.execute(insert_sql, (
        event_info["이미지 주소"],
        event_info["이벤트 시작 날짜"],
        event_info["이벤트 끝 날짜"],
        event_info["이벤트 제목"],
        event_info["편의점"]
    ))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ 이벤트 저장 완료: {event_info['이벤트 제목']}")


def scrape_event_page(driver):
    """이벤트 상세 페이지 크롤링"""
    try:
        title = driver.find_element(By.CSS_SELECTOR, ".tit_sect h3.tit strong").text
        start_date = driver.find_element(By.ID, "event-start-date").text
        end_date = driver.find_element(By.ID, "event-end-date").text
        image_url = driver.find_element(By.CSS_SELECTOR, ".event-web-contents img").get_attribute("src")

        event_info = {
            "이벤트 제목": title,
            "이벤트 시작 날짜": start_date,
            "이벤트 끝 날짜": end_date,
            "이미지 주소": image_url,
            "편의점": "GS25"
        }

        save_to_db(event_info)  # DB 저장
    except Exception as e:
        print("Error scraping event page:", e)


def _scrape_gs25_events(driver):
    """GS25 이벤트 첫 페이지 크롤링 (한 페이지만)"""
    driver.get(base_url)
    time.sleep(3)

    event_list = driver.find_elements(By.CSS_SELECTOR, ".tblwrap tbody tr")
    
    if not event_list:
        print("⚠ 이벤트 없음. 크롤링 종료")
        return
    
    for i in range(len(event_list)):
        try:
            driver.get(base_url)
            time.sleep(3)

            event_list = driver.find_elements(By.CSS_SELECTOR, ".tblwrap tbody tr")

            # 특정 행에 링크가 없으면 건너뛰기
            event_links = event_list[i].find_elements(By.CSS_SELECTOR, "td.ft_lt a")  
            if not event_links:
                print(f"⚠ {i+1}번째 이벤트에 링크가 없음, 건너뜀")
                continue  

            event_link = event_links[0]  # 첫 번째 링크 클릭
            event_link.click()
            time.sleep(3)

            scrape_event_page(driver)  # 데이터 크롤링 및 저장

            driver.back()
            time.sleep(3)

        except Exception as e:
            print(f"❌ Error processing event {i+1}: {e}")
    print("✅ 크롤링 완료.")


def scrape_gs25_events():
    options = Options()
    for flag in ("--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"):
        options.add_argument(flag)
    driver = webdriver.Chrome(service=Service(chrome_driver_path()), options=options)
    try:
        return _scrape_gs25_events(driver)
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_gs25_events()
