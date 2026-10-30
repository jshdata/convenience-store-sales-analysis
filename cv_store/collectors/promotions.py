"""plus_schedule.py에서 분리한 수집기. import 시 수집·DB 연결을 실행하지 않습니다."""
from cv_store.database.connection import connect_db

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
base_urls = {
    "GS25": "https://pyony.com/brands/gs25/?page=",
    "CU": "https://pyony.com/brands/cu/?page=",
    "Seven": "https://pyony.com/brands/seven/?page="
}
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def format_update_date(date_str):
    if "." in date_str:
        current_year = datetime.now().year
        return f"{current_year}-{date_str.replace('.', '-')}"
    return date_str


def format_price(price_str):
    price_match = re.search(r"\d+", price_str.replace(",", ""))
    return int(price_match.group()) if price_match else 0


def get_latest_update_date(brand):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(update_date) FROM event_plus WHERE store_type = %s", (brand,))
    latest_date = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return latest_date.strftime("%Y-%m-%d") if latest_date else "2000-01-01"


def run_crawling(brand):
    print(f"🔍 {brand} 크롤링 시작...")

    base_url = base_urls[brand]
    latest_update_date = get_latest_update_date(brand)
    print(f"📅 {brand} 최신 업데이트 날짜: {latest_update_date}")

    page = 1
    previous_page_content = None
    new_data = []
    reached_existing = False

    while True:
        print(f"📄 {brand} {page} 페이지 크롤링 중...")
        url = f"{base_url}{page}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"❌ 요청 실패: {e}")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", class_="col-md-6")

        if not items:
            print(f"🚨 {brand} 마지막 페이지입니다. 크롤링 종료.")
            break

        current_page_products = "".join(str(item) for item in items)
        if previous_page_content == current_page_products:
            print(f"🚨 {brand} 현재 페이지는 이전 페이지와 동일합니다. 크롤링 완료!")
            break

        for item in items:
            update_date = item.find("small", class_="float-right text-white mr-3")
            title = item.find("strong")
            price_tag = item.find("i", class_="fa-coins")
            price = price_tag.next_sibling.strip() if price_tag else "0원"
            event_price_tag = item.find("span", class_="text-muted small")

            # 브랜드별 이벤트 타입 클래스 설정
            if brand == "GS25":
                plus_type_tag = item.find("span", class_="badge bg-gs25 text-white")
            elif brand == "CU":
                plus_type_tag = item.find("span", class_="badge bg-cu text-white")
            else:
                plus_type_tag = item.find("span", class_="badge bg-seven text-white")

            update_date_text = update_date.get_text(strip=True) if update_date else "날짜 없음"
            formatted_update_date = format_update_date(update_date_text)

            if formatted_update_date <= latest_update_date:
                print(f"✅ {brand} 이미 저장된 최신 업데이트 날짜 이후 데이터가 없습니다. 크롤링 종료.")
                reached_existing = True
                break

            formatted_price = format_price(price)
            formatted_event_price = format_price(event_price_tag.get_text(strip=True).strip("() ")) if event_price_tag else 0

            new_data.append((
                brand,
                formatted_update_date,
                title.get_text(strip=True) if title else "제목 없음",
                formatted_price,
                formatted_event_price,
                plus_type_tag.get_text(strip=True) if plus_type_tag else "이벤트 없음"
            ))

        if reached_existing:
            break
        previous_page_content = current_page_products
        page += 1

    if new_data:
        print(f"📌 {brand} 새로운 데이터 {len(new_data)}개를 DB에 저장합니다.")
        conn = connect_db()
        cursor = conn.cursor()
        
        insert_sql = """
        INSERT INTO event_plus (store_type, update_date, plus_title, plus_price, plus_event_price, plus_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.executemany(insert_sql, new_data)
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ {brand} DB 업데이트 완료!")
    else:
        print(f"✅ {brand} 새로운 데이터가 없습니다. 업데이트하지 않습니다.")


def check_and_run_crawling():
    print("🕛 자정 크롤링 확인 시작...")
    for brand in base_urls.keys():
        latest_update_date = get_latest_update_date(brand)
        print(f"🔍 {brand}의 최신 업데이트 날짜: {latest_update_date}")

        # 웹사이트에서 최신 업데이트 날짜 확인
        url = f"{base_urls[brand]}1"  # 첫 번째 페이지만 확인
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        update_date = soup.find("small", class_="float-right text-white mr-3")

        if update_date:
            new_update_date = format_update_date(update_date.get_text(strip=True))
            if new_update_date > latest_update_date:
                print(f"🚀 {brand} 업데이트 감지됨! 크롤링 시작")
                run_crawling(brand)
            else:
                print(f"✅ {brand} 업데이트 변경 없음.")
        else:
            print(f"⚠️ {brand}에서 업데이트 날짜를 찾을 수 없음.")


if __name__ == "__main__":
    check_and_run_crawling()
