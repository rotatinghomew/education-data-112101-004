"""分析结果落盘：CSV 明细表 + JSON 审计 + Markdown 摘要。

所有输出按稳定键排序，保证同一份输入反复重跑产生字节级一致
的结果，便于团队在更新处置记录与排班后做前后对比。
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path

from .arrivals import ArrivalForecast
from .links import HouseholdCluster, LinkReviewItem
from .projection import (
    CategoryBacklog,
    ProjectionRow,
    StaffingRecommendation,
)
from .quality import QualityFlag
from .throughput import ThroughputEstimate
from .timeline import CaseState


def _convert(value):
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ";".join(str(v) for v in value)
    return value


def write_csv(path: Path, rows: list) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    if is_dataclass(rows[0]):
        fieldnames = list(asdict(rows[0]).keys())
        records = [asdict(row) for row in rows]
    else:
        fieldnames = list(rows[0].keys())
        records = rows
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: _convert(record[k]) for k in fieldnames})


def case_state_rows(states: dict[str, CaseState]) -> list[dict]:
    rows = []
    for ref in sorted(states):
        state = states[ref]
        rows.append({
            "complaint_ref": ref,
            "category": state.complaint.category,
            "household_ref": state.complaint.household_ref,
            "impact_band": state.complaint.impact_band,
            "submitted_at": state.complaint.submitted_at,
            "stage": state.stage,
            "wait_owner": state.wait_owner,
            "current_team": state.current_team,
            "resolved": state.resolved,
            "terminal_event": state.terminal_event,
            "age_days": state.age_days,
            "internal_wait_age_days": state.internal_wait_age_days,
            "external_wait_age_days": state.external_wait_age_days,
            "internal_handling_days": round(state.internal_days, 2),
            "external_wait_days": round(state.external_wait_days, 2),
            "open_internal_days": round(state.open_internal_days, 2),
            "open_external_days": round(state.open_external_days, 2),
            "event_chain": " -> ".join(
                f"{e.event_type}@{e.event_at.isoformat() if e.event_at else 'NA'}"
                for e in state.ordered_events
            ),
            "timeline_flags": ";".join(state.timeline_flags),
        })
    return rows


def cluster_rows(clusters: dict[str, HouseholdCluster]) -> list[dict]:
    seen: set[str] = set()
    rows = []
    for ref in sorted(clusters):
        cluster = clusters[ref]
        if cluster.cluster_id in seen:
            continue
        seen.add(cluster.cluster_id)
        rows.append({
            "cluster_id": cluster.cluster_id,
            "complaint_refs": cluster.complaint_refs,
            "household_refs": cluster.household_refs,
            "confirmed_links": cluster.confirmed_links,
            "open_complaint_count": cluster.open_complaint_count,
            "open_household_count": cluster.open_household_count,
        })
    return rows


def review_rows(items: list[LinkReviewItem]) -> list[dict]:
    return [asdict(item) for item in sorted(
        items, key=lambda i: (i.left_ref, i.right_ref)
    )]


def evidence_rows(evidence_lookup: dict[str, dict]) -> list[dict]:
    rows = []
    for ref in sorted(evidence_lookup):
        row = {"complaint_ref": ref}
        row.update(evidence_lookup[ref])
        rows.append(row)
    return rows


def backlog_rows(buckets: dict[str, CategoryBacklog]) -> list[dict]:
    return [asdict(buckets[key]) for key in sorted(buckets)]


def forecast_rows(forecasts: dict[str, ArrivalForecast]) -> list[dict]:
    return [asdict(forecasts[key]) for key in sorted(forecasts)]


def write_audit_json(
    path: Path,
    payload: dict,
) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_convert),
        encoding="utf-8",
    )


def write_markdown_summary(
    path: Path,
    as_of,
    states: dict[str, CaseState],
    buckets: dict[str, CategoryBacklog],
    forecasts: dict[str, ArrivalForecast],
    throughput: dict[str, ThroughputEstimate],
    projection_rows: list[ProjectionRow],
    recommendations: list[StaffingRecommendation],
    flags: list[QualityFlag],
    meta: dict,
) -> None:
    lines: list[str] = []
    lines.append("# 投诉积压与排班分析摘要（自动生成，可重跑）")
    lines.append("")
    lines.append(f"- 分析基准日：`{as_of.isoformat()}`")
    lines.append(f"- 投影周期：{', '.join(meta['projected_periods'])}")
    lines.append("- 估计为供人员核查的区间值；资料缺失按保守口径处理，不等于低风险")
    lines.append("")

    open_cases = [s for s in states.values() if not s.resolved]
    internal = sum(1 for s in open_cases if s.wait_owner == "internal")
    external = sum(1 for s in open_cases if s.wait_owner == "external")
    lines.append("## 1. 当前队列")
    lines.append("")
    lines.append(f"- 未结个案 {len(open_cases)} 件：等内部判断 {internal} 件，"
                 f"等消费者补件 {external} 件；已结 {sum(1 for s in states.values() if s.resolved)} 件")
    lines.append("")
    lines.append("| 类别 | 内部待办 | 外部等待 | 未结独立家庭 | 负责团队 | 路由依据 |")
    lines.append("|---|---|---|---|---|---|")
    for key in sorted(buckets):
        b = buckets[key]
        lines.append(
            f"| {b.category} | {b.internal_open_cases} | {b.external_open_cases} | "
            f"{b.open_independent_households} | {', '.join(b.responsible_teams) or '未路由'} | "
            f"{b.routing_basis} |"
        )
    lines.append("")

    lines.append("## 2. 到达预测（每周期件数，低/中/高）")
    lines.append("")
    lines.append("| 类别 | 依据 | 低 | 中 | 高 | 独立家庭(中) | 历史趋势斜率 |")
    lines.append("|---|---|---|---|---|---|---|")
    for key in sorted(forecasts):
        f = forecasts[key]
        lines.append(
            f"| {f.category} | {f.basis} | {f.low} | {f.central} | {f.high} | "
            f"{f.household_central} | {f.trend_slope} |"
        )
    lines.append("")

    lines.append("## 3. 历史办案过程与人均周产能")
    lines.append("")
    lines.append("| 团队 | 专长 | 依据 | 单件天数(低/中/高) | 人均周产能(低/中/高) | 备注 |")
    lines.append("|---|---|---|---|---|---|")
    for team in sorted(throughput):
        e = throughput[team]
        lines.append(
            f"| {e.team_ref} | {e.specialty} | {e.basis} | "
            f"{e.handling_days_low}/{e.handling_days_central}/{e.handling_days_high} | "
            f"{e.per_person_throughput_low}/{e.per_person_throughput_central}/{e.per_person_throughput_high} | "
            f"{'；'.join(e.notes)} |"
        )
    lines.append("")

    lines.append("## 4. 分周期积压投影（期末内部积压）")
    lines.append("")
    lines.append("| 周期 | 类别 | 团队 | 情景 | 新增 | 补件回流 | 内部需求 | 估计产能 | 期末内部积压 | 期末外部等待 | 标记 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for row in projection_rows:
        cap = "" if row.capacity_estimate_cases is None else row.capacity_estimate_cases
        lines.append(
            f"| {row.period} | {row.category} | {row.team_ref} | {row.scenario} | "
            f"{row.arrivals} | {row.external_returns} | {row.internal_demand} | {cap} | "
            f"{row.ending_internal_backlog} | {row.ending_external_waiting} | {row.flags} |"
        )
    lines.append("")

    lines.append("## 5. 人员安排建议（相对最近一期已排人数）")
    lines.append("")
    lines.append("| 类别 | 团队 | 情景 | 已排人数 | 跟上来量需人 | 清积压加人 | 建议人数 | 缺口 | 依据标记 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for rec in recommendations:
        lines.append(
            f"| {rec.category} | {rec.team_ref} | {rec.scenario} | "
            f"{rec.planned_people if rec.planned_people is not None else '未知'} | "
            f"{rec.keep_up_people} | {rec.clear_backlog_surcharge_people} | "
            f"{rec.recommended_people} | "
            f"{rec.gap_vs_planned if rec.gap_vs_planned is not None else '无法比较'} | "
            f"{rec.rationale_flags} |"
        )
    lines.append("")

    gap_flags = [f for f in flags if f.severity == "gap"]
    warn_flags = [f for f in flags if f.severity == "warning"]
    lines.append("## 6. 数据缺口与质量标记")
    lines.append("")
    lines.append(f"- 缺口（gap）{len(gap_flags)} 条，警告（warning）{len(warn_flags)} 条，"
                 f"详见 `data_quality_flags.csv`")
    for flag in (gap_flags + warn_flags)[:12]:
        lines.append(f"  - [{flag.severity}] {flag.flag_code} · {flag.subject_type}:"
                     f"{flag.subject_ref} — {flag.detail}")
    lines.append("")
    lines.append("## 7. 重跑方式")
    lines.append("")
    lines.append("更新 `data/` 后执行：")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 -I run_analysis.py --data-dir data --output-dir outputs")
    lines.append("```")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
