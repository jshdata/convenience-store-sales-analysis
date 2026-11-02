"""Plotly 그래프. 조회와 외부 연결은 수행하지 않습니다."""

from cv_store.analysis.anomalies import ANOMALY_THRESHOLDS
from cv_store.dashboard.model import BRANDS, LABELS, pairwise_growth, sales_shares

COLORS = {"CU": "#7257B5", "GS25": "#3193BE", "seven": "#007F65"}
SIGNALS = {"high": "#CE594B", "low": "#467EB5", "normal": "#C2C9C7", "missing": "#C2C9C7"}


def style(fig, height=340):
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=10, r=15, t=25, b=15),
        font=dict(family="Malgun Gothic, sans-serif", color="#243D37", size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.13, title=None), hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E8EEEB", zerolinecolor="#C9D5CF")
    return fig


def sales_trend(frame, brands):
    import plotly.graph_objects as go
    fig = go.Figure()
    for brand in brands:
        data = frame[frame["store_type"] == brand]
        fig.add_trace(go.Scatter(
            x=data["sale_date"], y=data["sum_amount"] / 100_000_000,
            name=LABELS[brand], mode="lines", line=dict(color=COLORS[brand], width=2.3),
            hovertemplate="%{y:,.2f}억 원<extra></extra>",
        ))
    fig.update_yaxes(title="매출 (억 원)")
    return style(fig)


def share_chart(frame):
    import plotly.graph_objects as go
    shares = sales_shares(frame)
    fig = go.Figure(go.Pie(
        labels=[LABELS[b] for b in BRANDS], values=[shares[b] for b in BRANDS],
        hole=.7, sort=False, marker=dict(colors=[COLORS[b] for b in BRANDS]),
        textinfo="label+percent", textposition="outside",
        hovertemplate="%{label}: %{value:.2f}%<extra></extra>",
    ))
    fig.update_layout(showlegend=False, annotations=[dict(text="3사 내<br>매출 비중", x=.5, y=.5, showarrow=False)])
    return style(fig)


def deviation_chart(frame, brand):
    import plotly.graph_objects as go
    data = frame[frame["store_type"] == brand]
    fig = go.Figure(go.Bar(
        x=data["sale_date"], y=data["growth_deviation"],
        marker_color=[SIGNALS[k] for k in data["kind"]],
        customdata=data[["status"]].values,
        hovertemplate="%{x|%Y-%m-%d}<br>편차 %{y:.3f}%p · %{customdata[0]}<extra></extra>",
        name=LABELS[brand],
    ))
    threshold = ANOMALY_THRESHOLDS[brand]
    for label, key in [("95백분위", "high"), ("5백분위", "low")]:
        fig.add_hline(y=threshold[key], line_color="#66936E", line_dash="solid", line_width=2,
                      annotation_text=f"{label} {threshold[key]:.3f}", annotation_position="top left")
    fig.update_yaxes(title="3사 평균 대비 편차 (%p)")
    return style(fig, 310)


def pairwise_chart(frame, first, second, extent, thresholds=None):
    import plotly.graph_objects as go

    data = pairwise_growth(frame, first, second)
    data["signal"] = [
        "상한 이상" if thresholds is not None and value >= thresholds["high"] else
        "하한 이하" if thresholds is not None and value <= thresholds["low"] else
        "범위 내" if thresholds is not None else "기준 미산출"
        for value in data["difference"]
    ]
    colors = {"상한 이상": SIGNALS["high"], "하한 이하": SIGNALS["low"],
              "범위 내": SIGNALS["normal"], "기준 미산출": SIGNALS["normal"]}
    fig = go.Figure(go.Bar(
        x=data["sale_date"], y=data["difference"],
        marker_color=[colors[signal] for signal in data["signal"]],
        customdata=data[["first_growth", "second_growth", "signal"]].values,
        hovertemplate=("%{x|%Y-%m-%d}<br>" + LABELS[first] + ": %{customdata[0]:.3f}%<br>"
                       + LABELS[second] + ": %{customdata[1]:.3f}%<br>차이: %{y:+.3f}%p"
                       + "<br>%{customdata[2]}<extra></extra>"),
        name=f"{LABELS[first]} − {LABELS[second]}",
    ))
    fig.add_hline(y=0, line_color="#71837A", line_width=1)
    if thresholds is not None:
        for label, key, position in [("95백분위", "high", "top right"), ("5백분위", "low", "bottom right")]:
            fig.add_hline(y=thresholds[key], line_color="#56815D", line_width=2, line_dash="solid",
                          annotation_text=f"{label} {thresholds[key]:+.3f}%p", annotation_position=position)
        extent = max(extent, abs(thresholds["low"]) * 1.2, abs(thresholds["high"]) * 1.2)
    fig.update_yaxes(title="증감률 차이 (%p)", range=[-extent, extent])
    fig.update_xaxes(tickformat="%m/%d")
    return style(fig, 250)
