"""로컬 Streamlit 화면. Slack 전송·스케줄러·데이터 쓰기를 실행하지 않습니다."""

from datetime import datetime, timedelta, timezone
import logging

from cv_store.database import repository
from cv_store.dashboard.model import BRANDS, LABELS, PAIRS, pairwise_growth, pairwise_thresholds, period_frame, safe_link, sales_frame, sales_shares
from cv_store.dashboard.settings import initial_filters, load_dashboard_secrets

logger = logging.getLogger(__name__)


def main():
    import pandas as pd
    import streamlit as st
    from cv_store.dashboard.charts import deviation_chart, pairwise_chart, sales_trend, share_chart

    st.set_page_config(page_title="세븐일레븐 매출 전략", page_icon="📊", layout="wide")
    load_dashboard_secrets(st.secrets)
    st.markdown("""<style>
        .block-container {padding-top: 2.2rem; max-width: 1480px;}
        h1 {letter-spacing: -.04em;} h2, h3 {letter-spacing: -.025em;}
        [data-testid="stMetricValue"] {font-size: 1.85rem;}
        [data-testid="stSidebar"] {border-right: 1px solid #dce5df;}
        @media (max-width: 1100px) {
            [data-testid="stMetricValue"] {font-size: 1.45rem;}
            h1 {font-size: 2rem;}
        }
    </style>""", unsafe_allow_html=True)

    @st.cache_data(ttl=300, show_spinner=False)
    def load_sales():
        return sales_frame(repository.get_dashboard_sales()), datetime.now(timezone(timedelta(hours=9)))

    @st.cache_data(ttl=300, show_spinner=False)
    def load_context(day, brand):
        return repository.get_dashboard_context(day, brand)

    st.sidebar.title("매출 전략 리서치")
    st.sidebar.caption("SEVEN-ELEVEN · COMPETITIVE INTELLIGENCE")
    if st.sidebar.button("데이터 새로고침", use_container_width=True):
        load_sales.clear()
        load_context.clear()
    try:
        with st.spinner("매출 데이터를 불러오는 중입니다…"):
            frame, loaded_at = load_sales()
    except Exception as exc:
        logger.error("Dashboard sales unavailable (%s)", type(exc).__name__)
        st.error("매출 데이터를 불러오지 못했습니다. DB 연결과 CA 인증서 설정을 확인해주세요.")
        st.stop()
    if frame.empty:
        st.info("DB에 조회 가능한 매출 데이터가 없습니다.")
        st.stop()

    first, last = frame["sale_date"].min().date(), frame["sale_date"].max().date()
    defaults, requested_brand, requested_event = initial_filters(first, last, st.query_params)
    chosen = st.sidebar.date_input(
        "조회 기간", value=defaults, min_value=first, max_value=last,
        format="YYYY-MM-DD",
    )
    selected = st.sidebar.multiselect("비교 브랜드", BRANDS, default=list(BRANDS), format_func=LABELS.get)
    if len(chosen) != 2:
        st.info("조회할 시작일과 종료일을 선택해주세요.")
        st.stop()
    if not selected:
        st.info("비교할 브랜드를 한 개 이상 선택해주세요.")
        st.stop()
    focus = st.sidebar.selectbox("상세 분석 브랜드", selected, index=selected.index(requested_brand) if requested_brand in selected else 0,
                                 format_func=LABELS.get)
    st.sidebar.divider()
    st.sidebar.caption(f"보유 기간\n\n{first:%Y.%m.%d} – {last:%Y.%m.%d}")
    st.sidebar.caption(f"DB 조회 시각 {loaded_at:%Y-%m-%d %H:%M} KST\n\n캐시 5분 · 새로고침으로 재조회")

    start, end = chosen
    period = period_frame(frame, start, end)
    visible = period[period["store_type"].isin(selected)].copy()
    focused = period[period["store_type"] == focus]
    if visible.empty or focused.empty:
        st.info("선택 기간에 해당 브랜드의 매출이 없습니다. 기간이나 브랜드를 변경해주세요.")
        st.stop()
    anomalies = visible[visible["kind"].isin(["high", "low"])].sort_values(
        ["sale_date", "store_type"], ascending=[False, True],
    )
    latest = focused.iloc[-1]
    st.caption("SEVEN-ELEVEN / SALES INTELLIGENCE")
    st.title("경쟁사의 변화를, 전략의 단서로")
    st.write("3사 매출 흐름과 평균 대비 편차를 비교하고, 이상 변동이 발생한 날의 뉴스와 영상을 살펴보세요.")
    st.caption(f"{start:%Y.%m.%d} — {end:%Y.%m.%d} · 상세 분석: {LABELS[focus]}")

    if (period.groupby("sale_date")["store_type"].nunique() < 3).any():
        st.warning("일부 날짜에 3사 데이터가 모두 존재하지 않습니다. 매출 비중 해석 시 확인해주세요.")
    with st.container(border=True):
        a, b = st.columns(2)
        a.metric(f"{LABELS[focus]} 기간 매출", f"{focused['sum_amount'].sum() / 100_000_000:,.1f}억 원")
        b.metric("3사 내 매출 비중", f"{sales_shares(period)[focus]:.2f}%")
        c, d = st.columns(2)
        c.metric("선택 브랜드 이상치", f"{len(anomalies):,}건")
        value = latest["growth_deviation"]
        d.metric("최근일 편차", "미산출" if pd.isna(value) else f"{value:+.2f}%p")
    st.caption(f"매출 비중은 제공받은 카드 집계 데이터의 3사 내 비율입니다. 전체 시장점유율이 아닙니다. 최근일: {latest['sale_date']:%Y-%m-%d}")

    trend, share = st.columns([2.2, 1])
    with trend:
        st.subheader("매출 흐름")
        st.plotly_chart(sales_trend(period, selected), use_container_width=True, key="sales_trend")
    with share:
        st.subheader("3사 매출 구성")
        st.plotly_chart(share_chart(period), use_container_width=True, key="sales_share")
    pair_tab, anomaly_tab = st.tabs(["브랜드 간 증감률 차이", "3사 평균 대비 이상치"])
    with pair_tab:
        st.subheader("경쟁사와의 증감률 차이")
        st.caption("앞 브랜드 증감률 − 뒤 브랜드 증감률입니다. 양수는 앞 브랜드가, 음수는 뒤 브랜드가 더 높다는 뜻입니다.")
        st.caption("초록 실선: 각 쌍의 2024년 전체 차이에서 구한 고정 5·95백분위 / 빨강: 상한 이상 · 파랑: 하한 이하 · 회색: 범위 내")
        pairs = [(a, b) for a, b in PAIRS if a in selected and b in selected]
        differences = [pairwise_growth(period, a, b)["difference"] for a, b in pairs]
        maxima = [float(values.abs().max()) for values in differences if not values.empty]
        extent = max(maxima, default=1) * 1.12 or 1
        if not pairs:
            st.info("브랜드 간 비교는 두 개 이상 선택해주세요. 3사를 선택하면 비교 그래프 3개가 표시됩니다.")
        for first_brand, second_brand in pairs:
            st.markdown(f"**{LABELS[first_brand]} − {LABELS[second_brand]}**")
            thresholds = pairwise_thresholds(frame, first_brand, second_brand)
            if thresholds is None:
                st.caption("2024년 비교 데이터가 없어 이 쌍의 기준선을 산출하지 못했습니다.")
            st.plotly_chart(pairwise_chart(period, first_brand, second_brand, extent, thresholds),
                            use_container_width=True, key=f"pair_{first_brand}_{second_brand}")
        st.caption("쌍별 기준은 새 비교 지표로, 기존 Slack의 브랜드−3사 평균 판정과 별개입니다. 조회 기간을 바꿔도 기준선은 유지됩니다.")
    with anomaly_tab:
        st.subheader(f"{LABELS[focus]} · 3사 평균 대비 편차")
        st.caption("빨강: 급등 · 파랑: 급감 · 회색: 정상 / 경계선: 2024년 전체 편차의 고정 5·95백분위 기준")
        st.plotly_chart(deviation_chart(period, focus), use_container_width=True, key="deviation")

    st.subheader("이상 변동 탐색")
    st.caption("표와 아래 선택 상자로 날짜를 살펴보세요. 판정 기준은 Slack 알림과 동일합니다.")
    if anomalies.empty:
        st.info("이 기간에는 선택 브랜드의 이상치가 없습니다. 최근일의 관련 자료를 표시합니다.")
        context_day, context_brand = latest["sale_date"].date().isoformat(), focus
    else:
        table = anomalies[["sale_date", "brand", "status", "sum_amount", "growth_deviation"]].rename(columns={
            "sale_date": "날짜", "brand": "브랜드", "status": "판정", "sum_amount": "매출액 (원)", "growth_deviation": "편차 (%p)",
        })
        st.dataframe(table, hide_index=True, use_container_width=True, height=250,
                     column_config={"날짜": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                    "매출액 (원)": st.column_config.NumberColumn(format="%d"),
                                    "편차 (%p)": st.column_config.NumberColumn(format="%.3f")})
        options = []
        option_labels = {}
        for row in anomalies.itertuples():
            option = f"{row.sale_date.date().isoformat()}|{row.store_type}"
            options.append(option)
            option_labels[option] = f"{row.sale_date:%Y-%m-%d} · {row.brand} · {row.status} · {row.growth_deviation:+.3f}%p"
        default_index = next((i for i, option in enumerate(options) if option.endswith("|" + focus)), 0)
        requested_option = f"{requested_event}|{focus}"
        if requested_option in options:
            default_index = options.index(requested_option)
        event = st.selectbox("관련 자료를 확인할 이상치", options, index=default_index, format_func=option_labels.get)
        context_day, context_brand = event.split("|")

    st.markdown(f"#### {context_day} · {LABELS[context_brand]} 관련 자료")
    st.caption("같은 날짜·브랜드로 저장된 자료입니다. 매출 변동의 원인으로 검증된 결과가 아닙니다.")
    try:
        context = load_context(context_day, context_brand)
    except Exception as exc:
        logger.error("Dashboard context unavailable (%s)", type(exc).__name__)
        st.warning("관련 자료를 불러오지 못했습니다. 매출 그래프는 계속 확인할 수 있습니다.")
    else:
        for column, key, title in zip(st.columns(2), ("news", "videos"), ("뉴스", "유튜브")):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    items = [item for item in context[key] if safe_link(item.get("url"))]
                    if not items:
                        st.caption("이 날짜에 저장된 자료가 없습니다.")
                    for item in items:
                        st.link_button(str(item.get("title") or "원문 보기"), safe_link(item["url"]), use_container_width=True)
                        if item.get("source"):
                            st.caption(str(item["source"]))
                    if len(context[key]) == 10:
                        st.caption("최대 10건을 표시합니다.")

    with st.expander("데이터와 판정 기준"):
        st.write("멘토를 통해 제공받은 비식별 카드 기반 집계 데이터로 3사 매출을 분석한 과거 프로젝트입니다.")
        st.write("편차 = 브랜드의 전날 대비 증감률 − 같은 날 3사 증감률의 산술평균. 단위는 %p입니다.")
        st.write("2024년 전체 편차의 5·95백분위수에 대응하는 기존 고정값을 사용합니다. 조회 기간을 바꿔도 경계선은 재계산하지 않습니다.")
        st.write("2024년 데이터에 같은 해 전체 기준을 적용한 결과는 회고적 분석이며 미래 정보 없이 수행한 성능 평가가 아닙니다.")
        st.write("이 화면은 조회 전용입니다. Slack 알림 발송이나 자동 시뮬레이션은 실행하지 않습니다.")
