"""홈 그래프 PNG와 짧은 수명의 메모리 저장소. URL 요청에서 DB를 조회하지 않습니다."""

from collections import OrderedDict
from datetime import date
from io import BytesIO
import secrets
from threading import Lock
import time


class ChartStore:
    def __init__(self, ttl=1800, capacity=32, clock=time.monotonic):
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self.items = OrderedDict()
        self.lock = Lock()

    def put(self, png):
        with self.lock:
            now = self.clock()
            self.items = OrderedDict((k, v) for k, v in self.items.items() if v[0] > now)
            token = secrets.token_hex(24)
            self.items[token] = (now + self.ttl, png)
            while len(self.items) > self.capacity:
                self.items.popitem(last=False)
            return token

    def get(self, token):
        with self.lock:
            entry = self.items.get(token)
            if entry is None:
                return None
            if entry[0] <= self.clock():
                self.items.pop(token, None)
                return None
            return entry[1]


chart_store = ChartStore()
render_lock = Lock()


def render_chart(series):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates

    active = [item for item in series if item["points"]]
    if not active:
        return None
    with render_lock:
        figure = Figure(figsize=(10, 2.8 * len(active)), dpi=120, layout="constrained")
        axes = figure.subplots(len(active), 1, squeeze=False).ravel()
        for ax, item in zip(axes, active):
            days, values = zip(*item["points"])
            limits = item["limits"]
            colors = ["#CE594B" if limits and value >= limits["high"] else
                      "#467EB5" if limits and value <= limits["low"] else "#BCC7C1" for value in values]
            ax.bar([date.fromisoformat(day) for day in days], values, color=colors, width=.8)
            ax.axhline(0, color="#9AA9A0", linewidth=.7)
            if limits:
                for key, label in [("high", "P95"), ("low", "P05")]:
                    ax.axhline(limits[key], color="#56815D", linewidth=1.5)
                    ax.text(.99, limits[key], f"{label} {limits[key]:+.3f}", ha="right", va="bottom" if key == "high" else "top",
                            transform=ax.get_yaxis_transform(), fontsize=8, color="#355A3E")
            ax.set_title(item["title"], loc="left", fontsize=11, fontweight="bold")
            ax.set_ylabel("Difference (pp)", fontsize=9)
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax.tick_params(labelsize=8)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_axisbelow(True)
            ax.grid(axis="y", color="#E5EBE7", linewidth=.6)
        output = BytesIO()
        FigureCanvasAgg(figure).print_png(output)
        figure.clear()
        return output.getvalue()
