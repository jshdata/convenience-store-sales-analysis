"""특정 날짜의 이상 매출을 조회하고 명시적으로 Slack에 전송합니다."""

from cv_store.analysis.anomalies import classify_anomaly
from cv_store.database import repository
from cv_store.integrations.slack.messages import format_news_links, format_ytb_links


def send_anomaly_alerts(client, channel, day):
    day = repository.validate_date(day)
    if not channel:
        raise ValueError("SLACK_CHANNEL_ALERT가 필요합니다.")
    sent = 0
    for row in repository.get_sales_for_date(day):
        store = row["store_type"]
        kind = classify_anomaly(store, row["growth_deviation"])
        if kind is None:
            continue
        videos, video_buttons = format_ytb_links(
            repository.get_ytb_links_by_date_and_store(day, store), day, store
        )
        news, news_buttons = format_news_links(
            repository.get_news_links_by_date_and_store(day, store), day, store
        )
        label = "🚨 매출 급등 감지!" if kind == "high" else "⚠️ 매출 급감 감지!"
        client.chat_postMessage(
            channel=channel,
            text=(
                f"{day} {store} {label}\n"
                f"💰 매출액: {row['sum_amount']:,.0f}원\n"
                f"📊 편차 (growth_deviation): {row['growth_deviation']:.2f}%\n\n"
                f"{videos}\n\n{news}"
            ),
            attachments=(video_buttons or []) + (news_buttons or []),
            unfurl_links=True,
            unfurl_media=True,
        )
        sent += 1
    return sent
