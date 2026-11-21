"""历史到达变化分析与未来周期预测。

只用标准库实现最小二乘趋势与样本标准差。对每个类别给出
低/中/高三档预测：

* 中档：对历史各期做线性趋势外推（样本期太短时退化为均值）；
* 低档/高档：在中档基础上结合历史残差波动取 ±1 个样本标准差，
  并以历史最小值/最大值作为合理性夹取边界。

独立家庭数按其占收到件数的历史比例同步外推，更正/撤销量
（correction_count）单列，不并入新到达需求。
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev

from .models import ArrivalRow, Dataset


@dataclass
class ArrivalForecast:
    category: str
    history_periods: list[str]
    history_received: list[int]
    history_households: list[int]
    trend_slope: float
    flat_mean: float
    central: int
    low: int
    high: int
    household_share: float
    household_central: int
    household_low: int
    household_high: int
    basis: str  # trend | flat_mean | no_history
    fallback_complaint_log_received: int | None = None


def _linear_fit(values: list[float]) -> tuple[float, float]:
    """返回 (斜率, 截距)，x 为 0..n-1。"""
    n = len(values)
    if n < 2:
        return 0.0, values[0] if values else 0.0
    xs = list(range(n))
    x_bar, y_bar = mean(xs), mean(values)
    denominator = sum((x - x_bar) ** 2 for x in xs)
    if denominator == 0:
        return 0.0, y_bar
    slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, values)) / denominator
    return slope, y_bar - slope * x_bar


def forecast_category(rows: list[ArrivalRow], cycles: int) -> ArrivalForecast | None:
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r.period)
    periods = [r.period for r in rows]
    received = [float(r.received_count) for r in rows]
    households = [float(r.independent_households) for r in rows]

    slope, intercept = _linear_fit(received)
    flat = mean(received)
    basis = "trend" if len(received) >= 3 and abs(slope) >= 0.1 else "flat_mean"
    spread = pstdev(received) if len(received) >= 2 else 0.0
    lo_hist, hi_hist = min(received), max(received)

    # 预测最后一个未来周期，给出该类别下周期级的需求区间
    x_future = len(received) + cycles - 1
    central = slope * x_future + intercept if basis == "trend" else flat
    low = max(0.0, min(central - spread, lo_hist))
    high = max(central + spread, hi_hist)

    shares = [
        (h / r) if r > 0 else 0.0
        for r, h in zip(received, households)
    ]
    household_share = mean(shares)
    household_central = central * household_share
    household_low = low * household_share
    household_high = high * household_share

    return ArrivalForecast(
        category=rows[0].category,
        history_periods=periods,
        history_received=[int(v) for v in received],
        history_households=[int(v) for v in households],
        trend_slope=round(slope, 4),
        flat_mean=round(flat, 2),
        central=max(0, round(central)),
        low=max(0, round(low)),
        high=max(0, round(high)),
        household_share=round(household_share, 4),
        household_central=max(0, round(household_central)),
        household_low=max(0, round(household_low)),
        household_high=max(0, round(household_high)),
        basis=basis,
    )


def build_arrival_forecasts(dataset: Dataset, cycles: int) -> dict[str, ArrivalForecast]:
    by_category: dict[str, list[ArrivalRow]] = {}
    for row in dataset.arrivals:
        by_category.setdefault(row.category, []).append(row)

    forecasts: dict[str, ArrivalForecast] = {}
    for category, rows in by_category.items():
        forecast = forecast_category(rows, cycles)
        if forecast is not None:
            forecasts[category] = forecast

    # complaints 登记台账覆盖的类别（如 renewal）可能没有到达汇总，
    # 用台账提交数给出弱兜底，并显式标注为兜底口径。
    arrival_categories = set(by_category)
    log_counts: dict[str, int] = {}
    for complaint in dataset.complaints:
        log_counts[complaint.category] = log_counts.get(complaint.category, 0) + 1
    for category, count in sorted(log_counts.items()):
        if category not in arrival_categories:
            forecasts[category] = ArrivalForecast(
                category=category,
                history_periods=[],
                history_received=[],
                history_households=[],
                trend_slope=0.0,
                flat_mean=float(count),
                central=count,
                low=count,
                high=count,
                household_share=1.0,
                household_central=count,
                household_low=count,
                household_high=count,
                basis="no_history",
                fallback_complaint_log_received=count,
            )
    return forecasts


def latest_arrival_period(dataset: Dataset) -> str | None:
    periods = sorted({r.period for r in dataset.arrivals})
    return periods[-1] if periods else None
