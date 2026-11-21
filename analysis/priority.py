"""个案优先级估计（供人员核查，不替代人工判断）。

评分由五个 0~1 因子加权组成，权重在 ``config.Config`` 中集中
管理。资料缺失（unknown/missing）一律走保守下限，绝不会因为
缺数据而得到低分；关联簇只提升影响范围因子，不重复计数。
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config, EVIDENCE_MISSING, EVIDENCE_UNKNOWN, WAIT_EXTERNAL
from .links import HouseholdCluster
from .timeline import CaseState


@dataclass
class PriorityRow:
    complaint_ref: str
    category: str
    team_ref: str
    stage: str
    wait_owner: str
    impact_band: str
    evidence_state: str
    cluster_id: str
    cluster_open_cases: int
    cluster_open_households: int
    internal_wait_age_days: int
    age_days: int
    factor_age: float
    factor_impact: float
    factor_readiness: float
    factor_scope: float
    factor_stage: float
    priority_score: float
    priority_band: str
    rationale: str
    caution_flags: str


_IMPACT_FACTORS = {"high": 1.0, "medium": 0.6, "low": 0.3}
_READINESS_FACTORS = {
    # 材料越齐全、越接近可处理状态，分值越高
    "complete": 1.0,
    "partial": 0.7,
    "unknown": 0.5,
    "missing": 0.5,
}
_STAGE_FACTORS = {
    # 内部可推进的阶段高于外部等待；new 无人接手同样需要关注
    "new": 0.8,
    "assigned": 0.9,
    "received_evidence": 1.0,
    "transferred": 0.85,
    "waiting_consumer": 0.4,
}


def _band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _score(
    states: dict[str, CaseState],
    clusters: dict[str, HouseholdCluster],
    config: Config,
    evidence_lookup: dict[str, dict[str, object]] | None,
) -> list[PriorityRow]:
    if evidence_lookup is None:
        evidence_lookup = {
            ref: {"evidence_state": state.complaint and "missing"}
            for ref, state in states.items()
        }
    rows: list[PriorityRow] = []
    weights = config.priority_weights

    for ref, state in sorted(states.items()):
        if state.resolved:
            continue
        complaint = state.complaint
        evidence_state = str(evidence_lookup.get(ref, {}).get("evidence_state", EVIDENCE_MISSING))
        cluster = clusters.get(ref)
        cluster_cases = cluster.open_complaint_count if cluster else 1
        cluster_households = cluster.open_household_count if cluster else 1

        # 1) 年龄：以内部等待年龄为主，整体年龄兜底
        age_basis = state.internal_wait_age_days or state.age_days
        factor_age = min(1.0, age_basis / config.age_reference_days)

        # 2) 影响带：unknown 不给低分，走保守值
        factor_impact = _IMPACT_FACTORS.get(
            complaint.impact_band, config.unknown_impact_factor
        )

        # 3) 材料就绪度：unknown/missing 均为保守下限 0.5
        factor_readiness = _READINESS_FACTORS.get(
            evidence_state, config.unknown_factor_floor
        )

        # 4) 影响范围：簇内独立家庭越多越高，封顶 1；
        #    重复反馈不重复计数，单户仍给基础值
        factor_scope = min(1.0, 0.4 + 0.2 * max(0, cluster_households - 1))

        # 5) 阶段：未知阶段按保守下限，外部等待显著低于内部可推进
        factor_stage = _STAGE_FACTORS.get(state.stage, config.unknown_factor_floor)

        score = (
            weights["age"] * factor_age
            + weights["impact"] * factor_impact
            + weights["readiness"] * factor_readiness
            + weights["scope"] * factor_scope
            + weights["stage"] * factor_stage
        )

        flags: list[str] = []
        if complaint.impact_band == "unknown":
            flags.append("impact_unknown_treated_conservatively")
        if evidence_state in (EVIDENCE_UNKNOWN, EVIDENCE_MISSING):
            flags.append(f"evidence_{evidence_state}_not_downgraded")
        if state.stage == "new" or "no_events" in state.timeline_flags:
            flags.append("never_assigned")
        if state.wait_owner == WAIT_EXTERNAL:
            flags.append("waiting_on_consumer")
        if state.unknown_event_types:
            flags.append("unknown_event_type")

        rationale = (
            f"age={factor_age:.2f}(内部等待{state.internal_wait_age_days}d/总龄{state.age_days}d); "
            f"impact={factor_impact:.2f}({complaint.impact_band}); "
            f"readiness={factor_readiness:.2f}({evidence_state}); "
            f"scope={factor_scope:.2f}(簇{cluster_households}户/{cluster_cases}案); "
            f"stage={factor_stage:.2f}({state.stage})"
        )

        rows.append(
            PriorityRow(
                complaint_ref=ref,
                category=complaint.category,
                team_ref=state.current_team,
                stage=state.stage,
                wait_owner=state.wait_owner,
                impact_band=complaint.impact_band,
                evidence_state=evidence_state,
                cluster_id=cluster.cluster_id if cluster else ref,
                cluster_open_cases=cluster_cases,
                cluster_open_households=cluster_households,
                internal_wait_age_days=state.internal_wait_age_days,
                age_days=state.age_days,
                factor_age=round(factor_age, 3),
                factor_impact=round(factor_impact, 3),
                factor_readiness=round(factor_readiness, 3),
                factor_scope=round(factor_scope, 3),
                factor_stage=round(factor_stage, 3),
                priority_score=round(score, 3),
                priority_band=_band(score),
                rationale=rationale,
                caution_flags=";".join(flags),
            )
        )

    rows.sort(key=lambda r: (-r.priority_score, r.complaint_ref))
    return rows


def build_priority_rows(
    states: dict[str, CaseState],
    clusters: dict[str, HouseholdCluster],
    evidence_lookup: dict[str, dict[str, object]],
    config: Config,
) -> list[PriorityRow]:
    return _score(states, clusters, config, evidence_lookup)
