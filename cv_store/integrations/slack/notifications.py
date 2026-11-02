"""특정 날짜의 이상 매출을 조회하고 명시적으로 Slack에 전송합니다."""

from cv_store.analysis.anomalies import classify_anomaly
from cv_store.database import repository
from cv_store.integrations.slack.messages import format_news_links, format_ytb_links
from cv_store.integrations.slack.dashboard import dashboard_url


def anomaly_payload(row, day, kind, simulation_id=None):
    """전송 없이 메시지를 구성합니다. 시뮬레이션은 실행 ID·기준일을 명시합니다."""
    store = row["store_type"]
    videos, video_buttons = format_ytb_links(repository.get_ytb_links_by_date_and_store(day, store), day, store)
    news, news_buttons = format_news_links(repository.get_news_links_by_date_and_store(day, store), day, store)
    label = "🚨 매출 급등 감지!" if kind == "high" else "⚠️ 매출 급감 감지!"
    attachments = (video_buttons or []) + (news_buttons or [])
    url = dashboard_url(day, store, as_of=day if simulation_id else None)
    if url:
        attachments.append({"fallback": "대시보드에서 해당 날짜 확인", "actions": [
            {"type": "button", "text": "대시보드에서 확인", "url": url},
        ]})
    prefix = f"[시뮬레이션 · {simulation_id[:8]}]\n" if simulation_id else ""
    return dict(
        text=(f"{prefix}{day} {store} {label}\n"
              f"💰 매출액: {row['sum_amount']:,.0f}원\n"
              f"📊 편차 (growth_deviation): {row['growth_deviation']:.2f}%p\n\n"
              f"{videos}\n\n{news}"),
        attachments=attachments, unfurl_links=True, unfurl_media=True,
    )


def send_anomaly_alerts(client, channel, day):
    day = repository.validate_date(day)
    if not channel:
        raise ValueError("SLACK_CHANNEL_ALERT가 필요합니다.")
    sent = 0
    for row in repository.get_sales_for_date(day):
        kind = classify_anomaly(row["store_type"], row["growth_deviation"])
        if kind is not None:
            client.chat_postMessage(channel=channel, **anomaly_payload(row, day, kind))
            sent += 1
    return sent
