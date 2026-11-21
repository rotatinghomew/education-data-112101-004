"""证据完整度评估。

口径：

* ``supersedes`` 指向的旧证据视为被取代，不再参与完整度判断；
* 存在任一 ``complete`` 且有效（未被取代）的证据 -> complete；
* 只有 partial -> partial；收到过证据但完整度均为 unknown ->
  unknown；没有任何证据记录 -> missing。
* unknown/missing 表示资料不足，优先级评分中按保守下限处理，
  不会因此判为低风险。
"""

from __future__ import annotations

from .config import (
    EVIDENCE_COMPLETE,
    EVIDENCE_MISSING,
    EVIDENCE_PARTIAL,
    EVIDENCE_UNKNOWN,
)
from .models import Dataset


def evaluate_evidence(dataset: Dataset) -> dict[str, dict[str, object]]:
    """返回每个个案的证据综合状态与明细。"""
    superseded: set[str] = set()
    by_case: dict[str, list] = {}
    for record in dataset.evidence:
        if record.supersedes:
            superseded.add(record.supersedes)
        by_case.setdefault(record.complaint_ref, []).append(record)

    result: dict[str, dict[str, object]] = {}
    for complaint_ref, records in by_case.items():
        effective = [r for r in records if r.evidence_ref not in superseded]
        states = {r.completeness for r in effective}
        if EVIDENCE_COMPLETE in states:
            overall = EVIDENCE_COMPLETE
        elif "partial" in states:
            overall = EVIDENCE_PARTIAL
        elif effective:
            overall = EVIDENCE_UNKNOWN
        else:
            overall = EVIDENCE_MISSING
        result[complaint_ref] = {
            "evidence_state": overall,
            "effective_count": len(effective),
            "superseded_count": len(records) - len(effective),
            "latest_evidence_at": max(
                (r.received_at for r in effective if r.received_at),
                default=None,
            ),
            "evidence_types": ";".join(sorted({r.evidence_type for r in effective})),
        }

    for complaint in dataset.complaints:
        result.setdefault(
            complaint.ref,
            {
                "evidence_state": EVIDENCE_MISSING,
                "effective_count": 0,
                "superseded_count": 0,
                "latest_evidence_at": None,
                "evidence_types": "",
            },
        )
    return result
