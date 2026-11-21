"""团队产能与历史办案过程估计。

关键区分：

* ``capacity.available_people`` 是**已安排人数**（已扣除
  planned_absence 的排班结果），不是每人固定处理件数；
* 每人每周产能 = 工作日 × 利用率 ÷ 单件内部办案天数，
  单件天数由各专长的历史时间线区间估计，外部等待天数剔除；
* 未结案区间是右截断样本，高端情景用放大系数处理，不确定性
  地板保证小样本不会报出“零误差”。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev

from .config import Config
from .models import CapacityRow, Dataset
from .timeline import CaseState


@dataclass
class ThroughputEstimate:
    team_ref: str
    specialty: str
    category: str
    internal_observed_days: list[float] = field(default_factory=list)
    closed_handling_days: list[float] = field(default_factory=list)
    censored_segment_count: int = 0
    handling_days_low: float = 0.0
    handling_days_central: float = 0.0
    handling_days_high: float = 0.0
    per_person_throughput_low: float = 0.0
    per_person_throughput_central: float = 0.0
    per_person_throughput_high: float = 0.0
    basis: str = "no_observation"
    notes: list[str] = field(default_factory=list)


def team_specialty_map(dataset: Dataset) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in sorted(dataset.capacity, key=lambda r: (r.team_ref, r.period)):
        mapping.setdefault(row.team_ref, row.specialty)
    # 事件里出现但排班表缺失的团队：专长未知，留给质量标记提示
    event_teams = {e.team_ref for e in dataset.events if e.team_ref}
    for team in event_teams:
        mapping.setdefault(team, "unknown")
    return mapping


def _category_for_team(specialty: str) -> str:
    # 排班表专长标签与投诉类别使用同一词表；unknown 无法映射
    return specialty if specialty in {"refund", "advice", "renewal"} else "unknown"


def estimate_throughput(
    dataset: Dataset,
    states: dict[str, CaseState],
    config: Config,
) -> dict[str, ThroughputEstimate]:
    specialty_map = team_specialty_map(dataset)
    teams = sorted(set(specialty_map))

    # 收集每个团队的内部区间
    internal_by_team: dict[str, list[float]] = {t: [] for t in teams}
    closed_by_team: dict[str, list[float]] = {t: [] for t in teams}
    censored_counts: dict[str, int] = {t: 0 for t in teams}

    for state in states.values():
        if state.resolved:
            closed_days = sum(
                seg.days for seg in state.segments
                if seg.kind == "internal" and not seg.censored
            )
            team = state.current_team or (
                state.segments[-1].team_ref if state.segments else ""
            )
            if team:
                closed_by_team.setdefault(team, []).append(closed_days)
        for seg in state.segments:
            if seg.kind != "internal":
                continue
            if seg.team_ref:
                internal_by_team.setdefault(seg.team_ref, []).append(seg.days)
                if seg.censored:
                    censored_counts[seg.team_ref] = censored_counts.get(seg.team_ref, 0) + 1

    estimates: dict[str, ThroughputEstimate] = {}
    for team in teams:
        specialty = specialty_map[team]
        observed = internal_by_team.get(team, [])
        closed = closed_by_team.get(team, [])
        est = ThroughputEstimate(
            team_ref=team,
            specialty=specialty,
            category=_category_for_team(specialty),
            internal_observed_days=[round(d, 2) for d in observed],
            closed_handling_days=[round(d, 2) for d in closed],
            censored_segment_count=censored_counts.get(team, 0),
        )

        if not observed and not closed:
            est.basis = "no_observation"
            est.notes.append("该团队在时间线中没有可观察的内部办案区间")
            estimates[team] = est
            continue

        sample = closed if closed else observed
        central_days = mean(sample)
        spread = pstdev(sample) if len(sample) >= 2 else 0.0
        est.basis = "closed_cases" if closed else "censored_segments_only"

        low_days = max(0.5, central_days - spread)
        high_days = central_days + spread + config.handling_uncertainty_floor_days
        if not closed:
            # 只有截断样本：真实办案时长只会更长
            high_days = max(high_days, central_days * config.censored_high_multiplier)
            est.notes.append("仅观察到未结案的截断区间，高端天数已放大处理")
        if len(sample) < 3:
            est.notes.append(f"样本仅 {len(sample)} 个，估计不确定性大")

        est.handling_days_low = round(low_days, 2)
        est.handling_days_central = round(central_days, 2)
        est.handling_days_high = round(high_days, 2)

        weekly_capacity_days = config.working_days_per_week
        est.per_person_throughput_low = round(
            weekly_capacity_days * config.utilization_low / high_days, 2
        )
        est.per_person_throughput_central = round(
            weekly_capacity_days * config.utilization_central / central_days, 2
        )
        est.per_person_throughput_high = round(
            weekly_capacity_days * config.utilization_high / low_days, 2
        )
        estimates[team] = est

    return estimates


def capacity_lookup(dataset: Dataset) -> dict[tuple[str, str], CapacityRow]:
    return {(row.period, row.team_ref): row for row in dataset.capacity}


def planned_people(
    lookup: dict[tuple[str, str], CapacityRow],
    period: str,
    team: str,
    fallback_period: str | None,
) -> tuple[int | None, bool, CapacityRow | None]:
    """返回 (人数, 是否使用了兜底周期, 排班行)。人数未知时为 None。"""
    row = lookup.get((period, team))
    if row is not None:
        return row.available_people, False, row
    if fallback_period is not None:
        row = lookup.get((fallback_period, team))
        if row is not None:
            return row.available_people, True, row
    return None, False, None
