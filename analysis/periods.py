"""ISO 周（``YYYY-Www``）周期工具。"""

from __future__ import annotations

from datetime import date, timedelta


def parse_iso_week(period: str) -> tuple[int, int]:
    try:
        year_text, week_text = period.split("-W")
        return int(year_text), int(week_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"周期标签应为 YYYY-Www 形式: {period!r}") from exc


def iso_week_of(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def next_period(period: str) -> str:
    year, week = parse_iso_week(period)
    # 取该周周一再前进 7 天，自动处理跨年
    monday = date.fromisocalendar(year, week, 1)
    nxt = monday + timedelta(days=7)
    iso = nxt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def future_periods(start_period: str, cycles: int) -> list[str]:
    periods: list[str] = []
    current = start_period
    for _ in range(cycles):
        current = next_period(current)
        periods.append(current)
    return periods


def period_start(period: str) -> date:
    year, week = parse_iso_week(period)
    return date.fromisocalendar(year, week, 1)
