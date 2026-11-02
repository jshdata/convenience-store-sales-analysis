"""Slack 홈에서 날짜 범위를 지정하고 명시적으로 하루씩 재생합니다."""

from datetime import date
import json
import logging
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cv_store.integrations.slack.home import plain, section
from cv_store.integrations.slack.home_data import HomeFilters, LABELS, load_snapshot
from cv_store.integrations.slack.home_charts import chart_store, render_chart
from cv_store.integrations.slack.dashboard import dashboard_url
from cv_store.simulation import service, store

logger = logging.getLogger(__name__)


def form_values(view):
    try:
        previous = json.loads(view.get("private_metadata") or "{}")
    except ValueError:
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    state = view.get("state", {}).get("values", {})
    dates = state.get("simulation_dates", {})
    selection = state.get("simulation_scope", {}).get("simulation_store", {}).get("selected_option") or {}
    return dict(
        start=dates.get("simulation_start", {}).get("selected_date") or previous.get("start") or "2024-11-20",
        end=dates.get("simulation_end", {}).get("selected_date") or previous.get("end") or "2024-11-22",
        scope=selection.get("value") or previous.get("scope") or "ALL",
    )


def build_view(values, run=None, preview=None, message=None, image_url=None):
    metadata = dict(surface="simulation", **values)
    if run:
        metadata["run_id"] = run["id"]
    blocks = [
        {"type": "header", "text": plain("날짜 지정 시뮬레이션")},
        section("*미리보기는 발송하지 않습니다.* 새 실행을 만든 뒤 *하루 진행*을 누를 때만 해당 날짜의 이상치 알림을 보냅니다."),
        {"type": "actions", "elements": [{"type": "button", "action_id": "simulation_back", "text": plain("매출 조회로 돌아가기")}]},
        {"type": "actions", "block_id": "simulation_dates", "elements": [
            {"type": "datepicker", "action_id": "simulation_start", "initial_date": values["start"], "placeholder": plain("시작일")},
            {"type": "datepicker", "action_id": "simulation_end", "initial_date": values["end"], "placeholder": plain("종료일")},
        ]},
    ]
    options = [{"text": plain("3사 모두"), "value": "ALL"}] + [{"text": plain(label), "value": brand} for brand, label in LABELS.items()]
    blocks.append({"type": "actions", "block_id": "simulation_scope", "elements": [
        {"type": "static_select", "action_id": "simulation_store", "options": options,
         "initial_option": next(option for option in options if option["value"] == values["scope"])},
        {"type": "button", "action_id": "simulation_preview", "text": plain("기간 미리보기"), "value": "preview"},
        {"type": "button", "action_id": "simulation_create", "text": plain("새 실행 만들기"), "value": "create"},
    ]})
    if message:
        blocks.append(section(message))
    if preview:
        blocks.append(section(f"*미리보기: {preview['start']} ~ {preview['end']}*\n{preview['days']}일 · 예상 알림 {len(preview['events'])}건 · 발송 없음"))
        events = preview["events"][:10]
        if events:
            blocks.append(section("\n".join(f"{e['day']} · {LABELS[e['store_type']]} · {'급등' if e['kind'] == 'high' else '급감'} · {e['deviation']:+.3f}%p" for e in events)))
            if len(preview["events"]) > 10:
                blocks.append(section("처음 10건을 표시합니다."))
    if run:
        days = (date.fromisoformat(run["end_day"]) - date.fromisoformat(run["start_day"])).days + 1
        status = {"ready": "다음 날 진행 대기", "processing": "처리 중", "completed": "완료", "attention": "발송 상태 확인 필요"}[run["status"]]
        label = "3사 모두" if run["store_scope"] == "ALL" else LABELS[run["store_scope"]]
        blocks += [{"type": "divider"}, section(
            f"*실행 {run['id'][:8]} · {status}*\n"
            f"고정 실행 기간: {run['start_day']} ~ {run['end_day']} · {label}\n"
            f"진행: {run['processed_days']}/{days}일 · 발송 완료: {run.get('sent_count', 0)}건\n"
            f"마지막 완료일: {run.get('last_day') or '아직 없음'} · 알림 채널: <#{run['channel_id']}>"
        )]
        actions = [{"type": "button", "action_id": "simulation_status", "text": plain("현재 상태 새로고침"), "value": run["id"]}]
        if run["status"] == "ready":
            blocks.append(section(f"*다음 검사 날짜: {run['next_day']}*\n날짜 입력을 바꿔도 현재 실행의 기간은 유지됩니다. 다른 기간은 새 실행을 만드세요."))
            actions.insert(0, {"type": "button", "action_id": "simulation_next", "style": "primary",
                               "text": plain("하루 진행 · 알림 전송"), "value": json.dumps({"run_id": run["id"], "day": run["next_day"]})})
        elif run["status"] in {"attention", "processing"}:
            blocks.append(section("처리 중이거나 전송 결과 확인이 필요한 요청은 자동 재발송하지 않습니다. 상태를 새로고침하고 알림 채널·서버 상태를 확인해주세요."))
        if run.get("last_day"):
            url = dashboard_url(run["last_day"], "seven" if run["store_scope"] == "ALL" else run["store_scope"], as_of=run["last_day"])
            if url:
                parts = urlsplit(url)
                query = dict(parse_qsl(parts.query))
                query.update(start=run["start_day"], end=run["last_day"])
                url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
                actions.append({"type": "button", "action_id": "simulation_dashboard", "text": plain("기준일까지 대시보드 보기"), "url": url})
        blocks.append({"type": "actions", "elements": actions})
        if image_url:
            blocks.append({"type": "image", "image_url": image_url, "alt_text": "시뮬레이션 마지막 완료일까지의 증감률 차이", "title": plain(f"{run['last_day']}까지의 매출 변동")})
        history = run.get("events", [])
        if history:
            states = {"sent": "발송 완료", "sending": "확인 필요", "unknown": "결과 불명"}
            blocks.append(section("*최근 발송 이력 · 최대 10건*\n" + "\n".join(
                f"{e['sale_day']} · {LABELS[e['store_type']]} · {e['deviation']:+.3f}%p · {states[e['status']]}" for e in history)))
    blocks.append(section("원본 매출은 변경하지 않습니다. 실행 상태와 발송 이력만 저장합니다.\n기준은 2024년 전체 편차의 고정 5·95백분위이며 과거 동작 재현입니다. 새 실행은 같은 날짜의 알림을 다시 보낼 수 있습니다."))
    return {"type": "home", "callback_id": "simulation_home", "private_metadata": json.dumps(metadata), "blocks": blocks}


def show(client, user, run_id=None, values=None, plan=None, message=None):
    use_run_values = values is None
    values = values or dict(start="2024-11-20", end="2024-11-22", scope="ALL")
    try:
        run = store.get_run(user, run_id)
        if run and use_run_values:
            values = dict(start=run["start_day"], end=run["end_day"], scope=run["store_scope"])
        image_url = None
        if run and run.get("last_day"):
            base = os.environ.get("SLACK_PUBLIC_BASE_URL", "").strip().rstrip("/")
            if urlsplit(base).scheme == "https":
                try:
                    snapshot = load_snapshot(HomeFilters(run["start_day"], run["last_day"], "seven" if run["store_scope"] == "ALL" else run["store_scope"]))
                    png = render_chart(snapshot["series"])
                    if png:
                        image_url = f"{base}/slack/home-chart/{chart_store.put(png)}.png"
                except Exception as chart_error:
                    logger.warning("Simulation chart unavailable (%s)", type(chart_error).__name__)
        view = build_view(values, run, plan, message, image_url)
    except Exception as exc:
        logger.error("Simulation home unavailable (%s)", type(exc).__name__)
        view = build_view(values, message="실행 상태를 불러오지 못했습니다. 시뮬레이션 테이블과 DB 연결을 확인해주세요.")
    client.views_publish(user_id=user, view=view)


def register_handlers(app):
    def opened(ack, body, client):
        ack()
        show(client, body["user"]["id"])

    def back(ack, body, client):
        ack()
        from cv_store.integrations.slack.home import update_home
        update_home(client, body["user"]["id"], HomeFilters())

    def action(ack, body, client):
        ack()
        user, view = body["user"]["id"], body.get("view") or {}
        values = form_values(view)
        selected = body["actions"][0]
        plan, message, run_id = None, None, None
        try:
            metadata = json.loads(view.get("private_metadata") or "{}")
            run_id = metadata.get("run_id")
            if selected["action_id"] == "simulation_preview":
                plan = service.preview(**values)
            elif selected["action_id"] == "simulation_create":
                run_id = service.create_run(user, **values)["id"]
                message = "새 실행을 만들었습니다. 아직 알림은 발송하지 않았습니다."
            elif selected["action_id"] == "simulation_next":
                requested = json.loads(selected["value"])
                run_id = requested["run_id"]
                result = service.advance_day(client, user, run_id, requested["day"])
                message = f"{result['day']} 처리 완료 · 알림 {result['sent']}건 발송."
            elif selected["action_id"] == "simulation_status":
                run_id = selected["value"]
        except store.StateChanged:
            message = "이미 처리했거나 진행 중인 날짜입니다. 현재 상태를 표시합니다. 추가 전송하지 않았습니다."
        except service.InputError as exc:
            # 사용자 입력 검증 메시지만 전달하고 DB/API 예외는 아래에서 가립니다.
            message = str(exc)
        except Exception as exc:
            logger.error("Simulation action stopped (%s)", type(exc).__name__)
            message = "처리를 완료하지 못했습니다. 현재 발송 상태를 확인해주세요. 자동 재발송하지 않습니다."
        show(client, user, run_id, values, plan, message)

    def acknowledge(ack):
        ack()

    app.action("simulation_open")(opened)
    app.action("simulation_back")(back)
    for name in ("simulation_preview", "simulation_create", "simulation_next", "simulation_status"):
        app.action(name)(action)
    for name in ("simulation_start", "simulation_end", "simulation_store", "simulation_dashboard"):
        app.action(name)(acknowledge)
