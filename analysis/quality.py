"""数据质量标记与建议可追溯事实。

分析不假设数据完整：每个缺口都形成一条质量标记，容量建议的
触发事实则汇总成审计记录，回答“这条建议由哪些到达、处理与
状态事实触发”。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .arrivals import ArrivalForecast
from .models import Dataset
from .throughput import ThroughputEstimate
from .timeline import CaseState


@dataclass
class QualityFlag:
    flag_code: str
    severity: str  # info | warning | gap
    subject_type: str
    subject_ref: str
    detail: str


def collect_quality_flags(
    dataset: Dataset,
    states: dict[str, CaseState],
    forecasts: dict[str, ArrivalForecast],
    throughput: dict[str, ThroughputEstimate],
) -> list[QualityFlag]:
    flags: list[QualityFlag] = []

    # 1) 个案时间线问题
    for ref, state in sorted(states.items()):
        for note in state.timeline_flags:
            severity = "gap" if note in {"no_events", "orphan_event"} else "warning"
            flags.append(QualityFlag(note, severity, "complaint", ref,
                                     f"时间线标记: {note}"))
        for event_type in state.unknown_event_types:
            flags.append(QualityFlag(
                "unknown_event_type", "warning", "complaint", ref,
                f"出现未登记事件类型 {event_type}，按内部事件处理，需人工确认口径",
            ))

    # 2) 关键字段缺失
    for complaint in dataset.complaints:
        if complaint.impact_band in {"", "unknown"}:
            flags.append(QualityFlag(
                "impact_band_unknown", "info", "complaint", complaint.ref,
                "影响带未知：优先级采用保守因子，不判为低风险",
            ))
        if complaint.submitted_at is None:
            flags.append(QualityFlag(
                "missing_submitted_at", "gap", "complaint", complaint.ref,
                "缺少提交时间，无法计算总等待年龄",
            ))

    # 3) 到达汇总与投诉台账的类别覆盖差异
    arrival_categories = {row.category for row in dataset.arrivals}
    complaint_categories = {c.category for c in dataset.complaints}
    for category in sorted(complaint_categories - arrival_categories):
        forecast = forecasts.get(category)
        detail = "到达汇总缺少该类别，预测仅来自投诉台账提交数（弱兜底）"
        if forecast is not None and forecast.fallback_complaint_log_received is not None:
            detail += f"，台账样本 {forecast.fallback_complaint_log_received} 件"
        flags.append(QualityFlag(
            "arrival_category_missing", "gap", "category", category, detail,
        ))

    # 4) 排班覆盖差异：事件中出现但排班表没有的团队
    capacity_teams = {row.team_ref for row in dataset.capacity}
    event_teams = {e.team_ref for e in dataset.events if e.team_ref}
    for team in sorted(event_teams - capacity_teams):
        flags.append(QualityFlag(
            "team_missing_from_capacity_schedule", "gap", "team", team,
            "该团队有处置事件但无任何排班人数，产能无法量化",
        ))

    # 5) 专长标签与实际处置类别不一致
    team_categories: dict[str, set[str]] = {}
    for state in states.values():
        for seg in state.segments:
            if seg.team_ref:
                team_categories.setdefault(seg.team_ref, set()).add(
                    state.complaint.category
                )
    declared = {}
    for row in dataset.capacity:
        declared.setdefault(row.team_ref, row.specialty)
    for team, categories in sorted(team_categories.items()):
        if team in declared and declared[team] not in categories:
            flags.append(QualityFlag(
                "specialty_label_mismatch", "warning", "team", team,
                f"排班专长标注为 {declared[team]}，实际处置类别为 {sorted(categories)}",
            ))

    # 6) 产能估计依据
    for team, est in sorted(throughput.items()):
        if est.basis == "no_observation":
            flags.append(QualityFlag(
                "no_throughput_observation", "gap", "team", team,
                "没有可观察的内部办案区间，无法估计人均产能",
            ))
        elif est.basis == "censored_segments_only":
            flags.append(QualityFlag(
                "censored_segments_only", "warning", "team", team,
                "只有未结案截断样本，高端办案天数已放大，见产能估计表",
            ))
        for note in est.notes:
            flags.append(QualityFlag(
                "throughput_note", "info", "team", team, note,
            ))

    # 7) 独立家庭数不高于收到件数的合理性检查
    for row in dataset.arrivals:
        if row.independent_households > row.received_count:
            flags.append(QualityFlag(
                "households_exceed_received", "warning", "arrival",
                f"{row.period}/{row.category}",
                "独立家庭数大于收到件数，需核对去重口径",
            ))
    return flags


@dataclass
class RecommendationAudit:
    category: str
    team_ref: str
    scenario: str
    trigger_facts: dict[str, object] = field(default_factory=dict)


def build_audit_facts(
    dataset: Dataset,
    states: dict[str, CaseState],
    forecasts: dict[str, ArrivalForecast],
    throughput: dict[str, ThroughputEstimate],
    backlog,
    projection_meta: dict[str, object],
) -> list[RecommendationAudit]:
    """为每个类别×情景整理一条可追溯事实链。"""
    audits: list[RecommendationAudit] = []
    for category, bucket in sorted(backlog.items()):
        forecast = forecasts.get(category)
        team = bucket.responsible_teams[0] if bucket.responsible_teams else "UNROUTED"
        est = throughput.get(team)
        arrival_rows = [
            {
                "period": r.period,
                "received": r.received_count,
                "independent_households": r.independent_households,
                "corrections": r.correction_count,
            }
            for r in dataset.arrivals if r.category == category
        ]
        capacity_rows = [
            {
                "period": r.period,
                "available_people": r.available_people,
                "planned_absence": r.planned_absence,
            }
            for r in dataset.capacity if r.team_ref == team
        ]
        open_refs = sorted(
            ref for ref, state in states.items()
            if not state.resolved and state.complaint.category == category
        )
        for scenario in ("pessimistic", "central", "optimistic"):
            facts = {
                "arrival_history": arrival_rows,
                "arrival_forecast": (
                    {
                        "basis": forecast.basis,
                        "low": forecast.low,
                        "central": forecast.central,
                        "high": forecast.high,
                        "trend_slope_per_period": forecast.trend_slope,
                        "household_share": forecast.household_share,
                    }
                    if forecast else None
                ),
                "current_backlog": {
                    "internal_open_cases": bucket.internal_open_cases,
                    "external_open_cases": bucket.external_open_cases,
                    "open_independent_households": bucket.open_independent_households,
                    "open_case_refs": open_refs,
                },
                "processing_observation": (
                    {
                        "basis": est.basis,
                        "closed_handling_days": est.closed_handling_days,
                        "censored_internal_days": est.internal_observed_days,
                        "handling_days_low_central_high": [
                            est.handling_days_low,
                            est.handling_days_central,
                            est.handling_days_high,
                        ],
                        "per_person_weekly_throughput_low_central_high": [
                            est.per_person_throughput_low,
                            est.per_person_throughput_central,
                            est.per_person_throughput_high,
                        ],
                    }
                    if est else None
                ),
                "capacity_schedule": capacity_rows,
                "external_lag_assumption_days":
                    projection_meta.get("external_lag_scenarios_days", {}),
                "scenario": scenario,
            }
            audits.append(RecommendationAudit(
                category=category, team_ref=team, scenario=scenario,
                trigger_facts=facts,
            ))
    return audits
