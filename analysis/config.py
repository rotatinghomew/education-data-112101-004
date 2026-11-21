"""分析参数与口径约定。

所有估计口径集中在此处，主管若要调整工作天数、利用率情景或
优先级权重，只改这一个文件即可，计算逻辑保持不变。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 已知的处置事件类型；未登记的新事件类型不会导致程序崩溃，
# 而是按内部事件处理并写入数据质量标记，提醒人工确认口径。
TERMINAL_EVENTS = frozenset({"closed", "withdrawn", "merged"})
EXTERNAL_WAIT_EVENT = "waiting_consumer"
KNOWN_EVENTS = frozenset(
    {
        "assigned",
        "waiting_consumer",
        "received_evidence",
        "transferred",
        "closed",
        "merged",
        "split",
        "withdrawn",
    }
)

# 证据综合状态：
# complete 有完整且未被取代的证据；partial 只有部分证据；
# unknown 收到证据但完整度未知；missing 没有任何证据记录。
EVIDENCE_COMPLETE = "complete"
EVIDENCE_PARTIAL = "partial"
EVIDENCE_UNKNOWN = "unknown"
EVIDENCE_MISSING = "missing"

# 等待归属：internal=等内部判断/排期；external=等消费者补件；
# resolved=已终结（关闭/撤回/合并）。
WAIT_INTERNAL = "internal"
WAIT_EXTERNAL = "external"
WAIT_RESOLVED = "resolved"


@dataclass(frozen=True)
class Config:
    # 向前投影的排期周期数（每周一个周期）
    cycles: int = 4
    # 每人每周可用于办案的工作日
    working_days_per_week: float = 5.0
    # 利用率三情景：低值用于保守产能、高值用于乐观产能
    utilization_low: float = 0.70
    utilization_central: float = 0.85
    utilization_high: float = 0.95
    # 内部等待天数达到该值时，年龄因子满分
    age_reference_days: int = 10
    # 期望在多少个周期内消化当前内部积压
    backlog_clear_cycles: int = 4
    # 外部等待样本不足时采用的兜底补件周期（天）
    default_external_lag_days: int = 7
    # 办案天数估计的不确定性地板（天），防止样本完全一致时误报为零误差
    handling_uncertainty_floor_days: float = 0.5
    # 仅有截断样本（案件尚未结案）时，高端办案天数放大系数
    censored_high_multiplier: float = 1.5
    # 优先级权重，合计为 1；因子均在 0~1 之间
    priority_weights: dict[str, float] = field(
        default_factory=lambda: {
            "age": 0.30,
            "impact": 0.25,
            "readiness": 0.15,
            "scope": 0.15,
            "stage": 0.15,
        }
    )
    # 资料缺失时的保守因子下限：缺失不等于低风险
    unknown_factor_floor: float = 0.5
    unknown_impact_factor: float = 0.6
