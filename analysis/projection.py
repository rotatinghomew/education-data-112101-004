"""未来排期周期的积压压力与人员负荷模拟。

模拟按“类别 -> 负责团队”逐周期推进，三个情景同时计算：

* ``pessimistic``（高积压压力）：到达取高档、补件提前回流、
  人均产能取低档；
* ``central``：全部中档；
* ``optimistic``（低积压压力）：到达取低档、人均产能取高档。

外部等待个案不占用当期产能，按历史补件时长估计回流周期后再
计入内部需求；当前内部积压在周期之间结转，保证队列动态可比，
而不是静态排行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev

from .arrivals import ArrivalForecast
from .config import Config, WAIT_EXTERNAL
from .periods import future_periods
from .throughput import (
    ThroughputEstimate,
    capacity_lookup,
    planned_people,
)
from .timeline import CaseState, observed_external_lags

SCENARIOS = ("pessimistic", "central", "optimistic")


@dataclass
class CategoryBacklog:
    category: str
    internal_open_cases: int
    external_open_cases: int
    open_independent_households: int
    external_wait_ages: list[int] = field(default_factory=list)
    responsible_teams: list[str] = field(default_factory=list)
    routing_basis: str = "observed"


@dataclass
class ProjectionRow:
    period: str
    category: str
    team_ref: str
    scenario: str
    arrivals: int
    external_returns: int
    starting_internal_backlog: int
    internal_demand: int
    planned_people: int | None
    capacity_estimate_cases: float | None
    processed_cases: int
    ending_internal_backlog: int
    ending_external_waiting: int
    capacity_source_period: str
    flags: str


@dataclass
class StaffingRecommendation:
    category: str
    team_ref: str
    scenario: str
    planned_people: int | None
    capacity_source_period: str
    keep_up_people: float
    clear_backlog_surcharge_people: float
    recommended_people: int
    gap_vs_planned: int | None
    rationale_flags: str


def current_backlog_by_category(
    states: dict[str, CaseState],
) -> dict[str, CategoryBacklog]:
    buckets: dict[str, CategoryBacklog] = {}
    seen_teams: dict[str, set[str]] = {}
    historical_teams: dict[str, set[str]] = {}
    households: dict[str, set[str]] = {}

    for ref, state in sorted(states.items()):
        category = state.complaint.category
        teams = {seg.team_ref for seg in state.segments if seg.team_ref}
        if state.current_team:
            teams.add(state.current_team)
        # 历史处置团队来自所有案件（含已结），用于未结案件无路由时兜底
        historical_teams.setdefault(category, set()).update(teams)
        if state.resolved:
            continue
        bucket = buckets.setdefault(
            category,
            CategoryBacklog(category=category, internal_open_cases=0,
                            external_open_cases=0, open_independent_households=0),
        )
        if state.wait_owner == WAIT_EXTERNAL:
            bucket.external_open_cases += 1
            bucket.external_wait_ages.append(state.external_wait_age_days)
        else:
            bucket.internal_open_cases += 1
        if state.complaint.household_ref:
            households.setdefault(category, set()).add(state.complaint.household_ref)
        seen_teams.setdefault(category, set()).update(teams)

    for category, bucket in buckets.items():
        bucket.open_independent_households = len(households.get(category, set()))
        bucket.responsible_teams = sorted(seen_teams.get(category, set()))
        if bucket.responsible_teams:
            bucket.routing_basis = "observed_on_open_cases"
        elif historical_teams.get(category):
            bucket.responsible_teams = sorted(historical_teams[category])
            bucket.routing_basis = "historical_closed_cases_only"
        else:
            bucket.routing_basis = "unrouted"
    return buckets


def _external_lag_scenarios(states: dict[str, CaseState], config: Config) -> dict[str, float]:
    lags = observed_external_lags(states)
    if not lags:
        central = float(config.default_external_lag_days)
        return {"pessimistic": central * 0.7, "central": central, "optimistic": central * 1.3}
    central = mean(lags)
    spread = pstdev(lags) if len(lags) >= 2 else 0.0
    return {
        # 悲观：补件提前回来，更早占用产能
        "pessimistic": max(1.0, central - spread),
        "central": central,
        "optimistic": central + spread + config.handling_uncertainty_floor_days,
    }


def _route_team(
    category: str,
    backlog: CategoryBacklog,
    throughput: dict[str, ThroughputEstimate],
) -> str:
    if backlog.responsible_teams:
        return backlog.responsible_teams[0]
    for team, est in sorted(throughput.items()):
        if est.category == category:
            return team
    return "UNROUTED"


def project(
    states: dict[str, CaseState],
    forecasts: dict[str, ArrivalForecast],
    throughput: dict[str, ThroughputEstimate],
    dataset,
    config: Config,
    latest_capacity_period: str | None,
) -> tuple[list[ProjectionRow], list[StaffingRecommendation], dict[str, object]]:
    backlogs = current_backlog_by_category(states)
    lag_scenarios = _external_lag_scenarios(states, config)
    lookup = capacity_lookup(dataset)
    periods = future_periods(
        latest_capacity_period or _period_from_states(states), config.cycles
    )

    # 情景参数
    arrival_pick = {
        "pessimistic": lambda f: f.high,
        "central": lambda f: f.central,
        "optimistic": lambda f: f.low,
    }
    throughput_pick = {
        "pessimistic": lambda e: e.per_person_throughput_low,
        "central": lambda e: e.per_person_throughput_central,
        "optimistic": lambda e: e.per_person_throughput_high,
    }

    projection_rows: list[ProjectionRow] = []
    recommendations: list[StaffingRecommendation] = []

    for category in sorted(backlogs):
        backlog = backlogs[category]
        team = _route_team(category, backlog, throughput)
        est = throughput.get(team)
        forecast = forecasts.get(category)

        # 外部回流按累计到期数分配到周期
        external_remaining = {s: list(backlog.external_wait_ages) for s in SCENARIOS}
        # 内部结转队列按情景独立维护
        carry = {s: backlog.internal_open_cases for s in SCENARIOS}
        external_open = {s: backlog.external_open_cases for s in SCENARIOS}

        keep_up_people: dict[str, list[float]] = {s: [] for s in SCENARIOS}

        for period in periods:
            planned, used_fallback, cap_row = planned_people(
                lookup, period, team, latest_capacity_period
            )
            if cap_row is None:
                source_period = "none"
            elif used_fallback:
                source_period = latest_capacity_period or "unknown"
            else:
                source_period = period
            flags: list[str] = []
            if planned is None:
                flags.append("no_planned_capacity")
            elif used_fallback:
                flags.append(f"capacity_extrapolated_from_{latest_capacity_period}")
            if forecast is None or forecast.basis == "no_history":
                flags.append("arrival_forecast_from_case_log_fallback")
            if est is None or est.basis == "no_observation":
                flags.append("no_throughput_observation")

            for scenario in SCENARIOS:
                arrivals = arrival_pick[scenario](forecast) if forecast else 0
                lag = lag_scenarios[scenario]
                ages = external_remaining[scenario]
                returned = 0
                still_waiting: list[int] = []
                for age in ages:
                    # 已等待年龄 + 本周期 7 天内达到补件时长即回流
                    if age + 7 >= lag:
                        returned += 1
                    else:
                        still_waiting.append(age + 7)
                external_remaining[scenario] = still_waiting
                external_open[scenario] = len(still_waiting)

                starting = carry[scenario]
                demand = starting + arrivals + returned

                per_person = throughput_pick[scenario](est) if est else 0.0
                if planned is not None and per_person > 0:
                    capacity_cases = round(planned * per_person, 2)
                    processed = min(demand, round(capacity_cases))
                else:
                    capacity_cases = None
                    processed = 0
                    if "capacity_not_quantifiable" not in flags:
                        flags.append("capacity_not_quantifiable")

                ending = demand - processed
                carry[scenario] = ending

                if per_person > 0:
                    keep_up_people[scenario].append(
                        (arrivals + returned) / per_person
                    )

                projection_rows.append(
                    ProjectionRow(
                        period=period,
                        category=category,
                        team_ref=team,
                        scenario=scenario,
                        arrivals=arrivals,
                        external_returns=returned,
                        starting_internal_backlog=starting,
                        internal_demand=demand,
                        planned_people=planned,
                        capacity_estimate_cases=capacity_cases,
                        processed_cases=processed,
                        ending_internal_backlog=ending,
                        ending_external_waiting=external_open[scenario],
                        capacity_source_period=source_period,
                        flags=";".join(flags),
                    )
                )

        # 人员建议：跟上来量 + 在约定周期内消化既有内部积压
        for scenario in SCENARIOS:
            per_person = throughput_pick[scenario](est) if est else 0.0
            avg_keep_up = (
                mean(keep_up_people[scenario]) if keep_up_people[scenario] else 0.0
            )
            surcharge = (
                backlog.internal_open_cases
                / (config.backlog_clear_cycles * per_person)
                if per_person > 0
                else 0.0
            )
            recommended = max(0, round(avg_keep_up + surcharge))
            gap = None
            planned_latest, _, latest_row = planned_people(
                lookup, periods[-1], team, latest_capacity_period
            )
            if planned_latest is not None:
                gap = recommended - planned_latest
            rec_source = (
                latest_capacity_period if latest_row is not None else "none"
            )
            rec_flags = _recommendation_flags(
                forecast, est, team, dataset, latest_capacity_period
            )
            recommendations.append(
                StaffingRecommendation(
                    category=category,
                    team_ref=team,
                    scenario=scenario,
                    planned_people=planned_latest,
                    capacity_source_period=rec_source or "unknown",
                    keep_up_people=round(avg_keep_up, 2),
                    clear_backlog_surcharge_people=round(surcharge, 2),
                    recommended_people=recommended,
                    gap_vs_planned=gap,
                    rationale_flags=";".join(rec_flags),
                )
            )

    meta = {
        "projected_periods": periods,
        "external_lag_scenarios_days": {k: round(v, 2) for k, v in lag_scenarios.items()},
    }
    return projection_rows, recommendations, meta


def _recommendation_flags(forecast, est, team, dataset, latest_period) -> list[str]:
    flags: list[str] = []
    if forecast is None or forecast.basis == "no_history":
        flags.append("arrival_forecast_from_case_log_fallback")
    if est is None or est.basis == "no_observation":
        flags.append("no_throughput_observation")
    elif est.basis == "censored_segments_only":
        flags.append("throughput_based_on_censored_segments")
    capacity_teams = {row.team_ref for row in dataset.capacity}
    if team not in capacity_teams:
        flags.append("team_missing_from_capacity_schedule")
    elif latest_period:
        flags.append(f"planned_people_latest_known_{latest_period}")
    return flags


def _period_from_states(states: dict[str, CaseState]) -> str:
    from .periods import iso_week_of

    dates = [s.last_event_date for s in states.values() if s.last_event_date]
    if not dates:
        raise ValueError("无法确定投影起点：缺少事件时间与排班周期")
    return iso_week_of(max(dates))
