"""Slack App Home 필터와 조회 결과 갱신. 채널 메시지는 보내지 않습니다."""

from datetime import datetime, timedelta, timezone
import logging
import json
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cv_store.integrations.slack.dashboard import dashboard_url
from cv_store.integrations.slack.home_data import LABELS, filters_from_view, load_snapshot
from cv_store.integrations.slack.home_charts import chart_store, render_chart

logger = logging.getLogger(__name__)


def plain(text):
    return {"type": "plain_text", "text": text, "emoji": True}


def section(text):
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", " ")


def external_url(filters):
    url = dashboard_url(store=filters.store)
    if not url:
        return None
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(start=filters.start, end=filters.end)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def build_view(filters, snapshot=None, image_url=None, error=None, loading=False):
    blocks = [{"type": "header", "text": plain("세븐일레븐 매출 전략")},
              section("날짜와 브랜드를 선택하고 *조회*를 눌러주세요. 매출·편차와 관련 자료를 이 홈 화면에서 확인할 수 있습니다.")]
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "action_id": "simulation_open", "text": plain("날짜 지정 시뮬레이션"), "value": "open"},
    ]})
    blocks.append({"type": "actions", "block_id": "home_dates", "elements": [
        {"type": "datepicker", "action_id": "home_start", "initial_date": filters.start, "placeholder": plain("시작일")},
        {"type": "datepicker", "action_id": "home_end", "initial_date": filters.end, "placeholder": plain("종료일")},
    ]})
    stores = [{"text": plain(label), "value": store} for store, label in LABELS.items()]
    modes = [{"text": plain("3쌍 증감률 비교"), "value": "pairs"}, {"text": plain("선택 브랜드 평균 대비 편차"), "value": "brand"}]
    blocks.append({"type": "actions", "block_id": "home_options", "elements": [
        {"type": "static_select", "action_id": "home_store", "options": stores,
         "initial_option": next(option for option in stores if option["value"] == filters.store)},
        {"type": "static_select", "action_id": "home_chart", "options": modes,
         "initial_option": next(option for option in modes if option["value"] == filters.chart)},
        {"type": "button", "action_id": "home_refresh", "text": plain("조회 / 새로고침"), "style": "primary", "value": "refresh"},
    ]})
    url = external_url(filters)
    if url:
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "action_id": "home_open_dashboard", "text": plain("Streamlit에서 상세 분석"), "url": url},
        ]})
    if loading:
        blocks.append(section("⏳ 데이터를 조회하고 그래프를 준비하고 있습니다…"))
    if error:
        blocks.append(section(error))
    if snapshot:
        latest = snapshot["latest"]
        blocks += [{"type": "divider"}, section(f"*{filters.start} ~ {filters.end} · {LABELS[filters.store]}*")]
        if not latest:
            blocks.append(section("선택 기간에 해당 브랜드의 매출이 없습니다. 기간을 변경해주세요."))
        else:
            deviation = latest["growth_deviation"]
            value = "미산출" if deviation is None else f"{deviation:+.3f}%p"
            blocks.append({"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*기간 매출*\n{snapshot['amount'] / 100_000_000:,.1f}억 원"},
                {"type": "mrkdwn", "text": f"*3사 내 매출 비중*\n{snapshot['share']:.2f}%"},
                {"type": "mrkdwn", "text": f"*선택 브랜드 이상치*\n{len(snapshot['anomalies'])}건"},
                {"type": "mrkdwn", "text": f"*최근일 편차 ({latest['day']})*\n{value}"},
            ]})
        if image_url:
            blocks.append({"type": "image", "image_url": image_url,
                           "alt_text": "선택 기간의 증감률 차이와 2024년 고정 5·95백분위 기준선",
                           "title": plain("증감률 차이와 이상 변동")})
        if filters.chart == "pairs":
            blocks.append(section("초록선: 쌍별 2024년 전체 차이의 5·95백분위. 빨강: 상한 이상 · 파랑: 하한 이하.\n쌍별 기준은 새 비교 지표이며, 아래 이상치 목록과 Slack 알림은 *브랜드−3사 평균* 기준입니다."))
        else:
            blocks.append(section("초록선: 2024년 전체 편차의 고정 5·95백분위. 빨강: 급등 · 파랑: 급감. Slack 알림과 같은 기준입니다."))
        anomalies = snapshot["anomalies"][:5]
        if anomalies:
            blocks.append(section("*최근 이상치 · 최대 5건*\n" + "\n".join(
                f"{'🔴 급등' if row['kind'] == 'high' else '🔵 급감'} · {row['day']} · {row['growth_deviation']:+.3f}%p" for row in anomalies)))
        elif latest:
            blocks.append(section("선택 기간에는 해당 브랜드의 평균 대비 이상치가 없습니다."))
        if snapshot["context_day"]:
            blocks.append(section(f"*{snapshot['context_day']} 관련 자료*\n같은 날짜·브랜드의 참고 자료입니다. 매출 변동의 원인으로 검증된 결과가 아닙니다."))
            for key, title in [("news", "뉴스"), ("videos", "유튜브")]:
                links = []
                for item in snapshot["context"][key]:
                    try:
                        parts = urlsplit(item.get("url") or "")
                    except ValueError:
                        continue
                    if parts.scheme in {"http", "https"} and parts.hostname and not parts.username:
                        links.append(f"<{escape(item['url'])}|{escape(item.get('title') or title)[:120]}>")
                blocks.append(section(f"*{title}*\n" + ("\n".join(links) or "저장된 자료가 없습니다.")))
        timestamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"조회 시각 {timestamp} · 과거 카드 집계 데이터의 3사 내 비교 · 전체 시장점유율 아님"}]})
    return {"type": "home", "callback_id": "sales_home", "private_metadata": filters.metadata(), "blocks": blocks}


def update_home(client, user, filters):
    try:
        filters = filters.validated()
        client.views_publish(user_id=user, view=build_view(filters, loading=True))
        snapshot = load_snapshot(filters)
        image_url = None
        base = os.environ.get("SLACK_PUBLIC_BASE_URL", "").strip().rstrip("/")
        parts = urlsplit(base)
        if parts.scheme == "https" and parts.hostname and not parts.username:
            png = render_chart(snapshot["series"])
            if png:
                token = chart_store.put(png)
                image_url = f"{base}/slack/home-chart/{token}.png"
        client.views_publish(user_id=user, view=build_view(filters, snapshot, image_url))
    except Exception as exc:
        # API 응답에는 홈 데이터와 이미지 접근 URL이 들어갈 수 있으므로 출력하지 않습니다.
        logger.error("Slack home update failed (%s)", type(exc).__name__)
        try:
            client.views_publish(user_id=user, view=build_view(filters, error="조회하지 못했습니다. 잠시 후 다시 조회해주세요."))
        except Exception as publish_error:
            logger.error("Slack home error view unavailable (%s)", type(publish_error).__name__)


def register_home_handlers(app):
    def opened(event, client):
        if event.get("tab") == "home":
            view = event.get("view") or {}
            try:
                metadata = json.loads(view.get("private_metadata") or "{}")
            except ValueError:
                metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}
            if metadata.get("surface") == "simulation":
                from cv_store.simulation.home import show, form_values
                show(client, event["user"], metadata.get("run_id"), form_values(view))
            else:
                update_home(client, event["user"], filters_from_view(view))

    def refresh(ack, body, client):
        ack()
        try:
            filters = filters_from_view(body.get("view") or {}, include_state=True)
        except (ValueError, TypeError):
            old = filters_from_view(body.get("view") or {})
            client.views_publish(user_id=body["user"]["id"], view=build_view(old, error="날짜 범위를 확인해주세요. 시작일은 종료일 이전이어야 합니다."))
            return
        update_home(client, body["user"]["id"], filters)

    def acknowledge(ack):
        ack()

    app.event("app_home_opened")(opened)
    app.action("home_refresh")(refresh)
    for action in ("home_start", "home_end", "home_store", "home_chart", "home_open_dashboard"):
        app.action(action)(acknowledge)
