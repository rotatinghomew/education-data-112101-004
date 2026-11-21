"""命令行入口：串联读取、重建、预测、投影、落盘的完整流程。

用法：
    python3 -I run_analysis.py --data-dir data --output-dir outputs
    python3 -I run_analysis.py --data-dir data --output-dir outputs --as-of 2026-02-23

输出文件均为可重跑产物，更新处置记录与排班后原样再跑即可。
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .arrivals import build_arrival_forecasts, latest_arrival_period
from .config import Config
from .evidence import evaluate_evidence
from .links import build_clusters
from .loading import DataFormatError, load_dataset
from .periods import iso_week_of
from .priority import build_priority_rows
from .projection import current_backlog_by_category, project
from .quality import build_audit_facts, collect_quality_flags
from .reporting import (
    backlog_rows,
    cluster_rows,
    evidence_rows,
    forecast_rows,
    write_audit_json,
    write_csv,
    write_markdown_summary,
)
from .throughput import estimate_throughput
from .timeline import build_case_states


def _default_as_of(dataset) -> date:
    event_dates = [e.event_at for e in dataset.events if e.event_at]
    if not event_dates:
        raise DataFormatError("事件表没有任何可用日期，无法确定分析基准日；请用 --as-of 指定")
    return max(event_dates)


def run(data_dir: str | Path, output_dir: str | Path, as_of: date | None,
        config: Config | None = None) -> Path:
    config = config or Config()
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(data_dir)
    as_of = as_of or _default_as_of(dataset)

    # 1) 时间线与当前阶段
    states = build_case_states(dataset, as_of)
    open_refs = {ref for ref, state in states.items() if not state.resolved}

    # 2) 证据与关联去重
    evidence_lookup = evaluate_evidence(dataset)
    clusters, review_queue = build_clusters(dataset, open_refs)

    # 3) 到达预测与产能估计
    forecasts = build_arrival_forecasts(dataset, config.cycles)
    throughput = estimate_throughput(dataset, states, config)

    # 4) 优先级
    priority_rows = build_priority_rows(states, clusters, evidence_lookup, config)

    # 5) 积压投影与人员建议
    latest_capacity_periods = sorted({r.period for r in dataset.capacity})
    latest_capacity_period = latest_capacity_periods[-1] if latest_capacity_periods else None
    projection_rows, recommendations, meta = project(
        states, forecasts, throughput, dataset, config, latest_capacity_period,
    )
    backlog = current_backlog_by_category(states)

    # 6) 质量标记与审计事实
    flags = collect_quality_flags(dataset, states, forecasts, throughput)
    audits = build_audit_facts(
        dataset, states, forecasts, throughput, backlog, meta,
    )

    # 7) 落盘
    from .reporting import case_state_rows, review_rows
    write_csv(output_dir / "case_states.csv", case_state_rows(states))
    write_csv(output_dir / "evidence_summary.csv", evidence_rows(evidence_lookup))
    write_csv(output_dir / "household_clusters.csv", cluster_rows(clusters))
    write_csv(output_dir / "link_review_queue.csv", review_rows(review_queue))
    write_csv(output_dir / "arrival_forecast.csv", forecast_rows(forecasts))
    write_csv(output_dir / "throughput_estimate.csv",
              [throughput[k] for k in sorted(throughput)])
    write_csv(output_dir / "current_backlog.csv", backlog_rows(backlog))
    write_csv(output_dir / "priority_ranking.csv", priority_rows)
    write_csv(output_dir / "backlog_projection.csv", projection_rows)
    write_csv(output_dir / "staffing_recommendation.csv", recommendations)
    write_csv(output_dir / "data_quality_flags.csv", flags)

    write_audit_json(output_dir / "recommendation_audit.json", {
        "as_of": as_of.isoformat(),
        "as_of_iso_week": iso_week_of(as_of),
        "latest_arrival_period": latest_arrival_period(dataset),
        "latest_capacity_period": latest_capacity_period,
        "projection_meta": meta,
        "config": {
            "cycles": config.cycles,
            "working_days_per_week": config.working_days_per_week,
            "utilization_low_central_high": [
                config.utilization_low, config.utilization_central, config.utilization_high,
            ],
            "backlog_clear_cycles": config.backlog_clear_cycles,
            "priority_weights": config.priority_weights,
            "unknown_factor_floor": config.unknown_factor_floor,
        },
        "audits": [
            {
                "category": a.category,
                "team_ref": a.team_ref,
                "scenario": a.scenario,
                "trigger_facts": a.trigger_facts,
            }
            for a in audits
        ],
    })

    write_markdown_summary(
        output_dir / "summary.md", as_of, states, backlog, forecasts,
        throughput, projection_rows, recommendations, flags, meta,
    )
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="投诉积压与排班分析（可重跑）")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None,
                        help="分析基准日 ISO 日期，默认取事件表最后日期")
    args = parser.parse_args(argv)
    try:
        out = run(args.data_dir, args.output_dir, args.as_of)
    except DataFormatError as exc:
        parser.exit(2, f"数据口径错误：{exc}\n")
    print(f"分析完成，结果写入: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
