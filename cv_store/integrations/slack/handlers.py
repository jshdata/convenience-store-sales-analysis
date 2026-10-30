"""채널별 멘션·더보기 처리. 모델과 자동 시뮬레이션에 의존하지 않습니다."""

import logging
import os
import re

from cv_store.database import repository
from cv_store.integrations.slack.messages import format_news_links, format_ytb_links

logger = logging.getLogger(__name__)


def handle_mention(event, say, channels):
    text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
    channel = event.get("channel")
    stores = {channels[name]: store for name, store in
              (("CU", "CU"), ("GS25", "GS25"), ("SEVEN", "seven")) if channels[name]}
    if channel == channels["TABLEAU"] and text in ("대시보드", "티피"):
        key = "TABLEAU_DASHBOARD_URL" if text == "대시보드" else "TABLEAU_TP_URL"
        url = os.environ.get(key, "").strip()
        say(f"📊 Tableau 링크: {url}" if url else f"{key} 설정이 필요합니다.")
        return

    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    brand = re.search(r"\b(GS25|CU|SEVEN)\b", text, re.IGNORECASE)
    if not match:
        say("사용법: `@봇 2024-10-02` 또는 `@봇 CU 2024-10-02`")
        return
    try:
        day = repository.validate_date(match.group())
        if channel in stores:
            store = stores[channel]
            data = repository.get_sales_data(day, store)
            if not data:
                say(f"{day} {store} 매출 데이터가 없습니다.")
                return
            say(
                f"📅 {day} {store} 매출 분석 📊\n"
                f"💰 매출액: {data['sum_amount']:,.0f}원\n"
                f"📈 전날 대비 상승률: {data['sum_amount_growth']:.2f}%\n"
                f"📊 3사 평균 상승률: {data['avg_sum_amount_growth']:.2f}%\n"
                f"⚠️ 평균 대비 차이: {data['growth_deviation']:.2f}%"
            )
        elif channel in (channels["YOUTUBE"], channels["NEWS"]):
            if not brand:
                say("브랜드와 날짜를 입력해주세요: `@봇 CU 2024-10-02`")
                return
            store = repository.normalize_store(brand.group())
            if channel == channels["YOUTUBE"]:
                links = repository.get_ytb_links_by_date_and_store(day, store)
                message, attachments = format_ytb_links(links, day, store)
            else:
                links = repository.get_news_links_by_date_and_store(day, store)
                message, attachments = format_news_links(links, day, store)
            say(text=message, attachments=attachments or [])
        else:
            say("이 채널에서는 요청을 처리할 수 없습니다.")
    except ValueError:
        say("날짜와 브랜드를 확인해주세요. 예: `CU 2024-10-02`")
    except Exception:
        logger.exception("Slack 조회 처리 실패")
        say("데이터 조회에 실패했습니다. 서버 로그와 DB 설정을 확인해주세요.")


def handle_more(ack, body, respond, kind):
    ack()
    try:
        day, store = body["actions"][0]["value"].split("|")
        query = (repository.get_ytb_links_by_date_and_store if kind == "youtube"
                 else repository.get_news_links_by_date_and_store)
        links = query(day, store)
        text = "\n".join(links[3:]) if len(links) > 3 else "더 이상 관련 링크가 없습니다."
        respond(text=text, replace_original=False, unfurl_links=True, unfurl_media=True)
    except Exception:
        logger.exception("Slack 더보기 처리 실패")
        respond(text="관련 링크를 조회하지 못했습니다.", replace_original=False)


def register_handlers(app, channels):
    def mention(event, say):
        return handle_mention(event, say, channels)

    def youtube(ack, body, respond):
        return handle_more(ack, body, respond, "youtube")

    def news(ack, body, respond):
        return handle_more(ack, body, respond, "news")

    app.event("app_mention")(mention)
    app.action("show_more_ytb")(youtube)
    app.action("show_more_news")(news)
