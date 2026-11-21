"""CSV 读取与口径校验。

空字段保留为 ``""``（资料未提供），只有具备明确数值语义的列
才转成整数。数值缺失或非法时不静默归零，而是抛出
``DataFormatError`` 让重跑过程显式失败。
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from .models import (
    ArrivalRow,
    CapacityRow,
    Complaint,
    Dataset,
    Event,
    EvidenceRecord,
    Link,
)

REQUIRED_FILES = (
    "complaints.csv",
    "events.csv",
    "evidence.csv",
    "links.csv",
    "arrivals.csv",
    "capacity.csv",
)


class DataFormatError(ValueError):
    """源数据缺少必需列、无法解析或数值语义不成立时抛出。"""


def _parse_date(value: str, context: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DataFormatError(f"{context} 的日期无法解析: {value!r}") from exc


def _parse_int(value: str, context: str) -> int:
    value = value.strip()
    if value == "":
        raise DataFormatError(f"{context} 的计数字段为空，不能当作零")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise DataFormatError(f"{context} 的计数字段不是整数: {value!r}") from exc
    if parsed < 0:
        raise DataFormatError(f"{context} 的计数字段为负数: {parsed}")
    return parsed


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise DataFormatError(f"找不到数据文件: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise DataFormatError(f"{path.name} 缺少表头")
        rows = list(reader)
    for row in rows:
        if set(row) != set(reader.fieldnames):
            raise DataFormatError(f"{path.name} 存在列数不一致的行")
    return rows


def _require(columns: set[str], expected: set[str], filename: str) -> None:
    missing = expected - columns
    if missing:
        raise DataFormatError(f"{filename} 缺少必需列: {sorted(missing)}")


def load_dataset(data_dir: str | Path) -> Dataset:
    """读取整个数据目录，返回结构化的 :class:`Dataset`。"""
    data_dir = Path(data_dir)
    dataset = Dataset()

    complaints_rows = _read_rows(data_dir / "complaints.csv")
    _require(
        set(complaints_rows[0]) if complaints_rows else set(),
        {
            "complaint_ref", "household_ref", "merchant_ref", "category",
            "impact_band", "submitted_at", "source_ref",
        },
        "complaints.csv",
    )
    for row in complaints_rows:
        dataset.complaints.append(
            Complaint(
                ref=row["complaint_ref"].strip(),
                household_ref=row["household_ref"].strip(),
                merchant_ref=row["merchant_ref"].strip(),
                category=row["category"].strip(),
                impact_band=row["impact_band"].strip() or "unknown",
                submitted_at=_parse_date(row["submitted_at"], row.get("complaint_ref", "")),
                source_ref=row["source_ref"].strip(),
            )
        )

    for row in _read_rows(data_dir / "events.csv"):
        _require(set(row), {"event_ref", "complaint_ref", "event_type", "event_at",
                            "team_ref", "detail"}, "events.csv")
        dataset.events.append(
            Event(
                event_ref=row["event_ref"].strip(),
                complaint_ref=row["complaint_ref"].strip(),
                event_type=row["event_type"].strip(),
                event_at=_parse_date(row["event_at"], row.get("event_ref", "")),
                team_ref=row["team_ref"].strip(),
                detail=row["detail"].strip(),
            )
        )

    for row in _read_rows(data_dir / "evidence.csv"):
        _require(set(row), {"evidence_ref", "complaint_ref", "received_at",
                            "evidence_type", "completeness", "supersedes"}, "evidence.csv")
        dataset.evidence.append(
            EvidenceRecord(
                evidence_ref=row["evidence_ref"].strip(),
                complaint_ref=row["complaint_ref"].strip(),
                received_at=_parse_date(row["received_at"], row.get("evidence_ref", "")),
                evidence_type=row["evidence_type"].strip(),
                completeness=row["completeness"].strip() or "unknown",
                supersedes=row["supersedes"].strip(),
            )
        )

    for row in _read_rows(data_dir / "links.csv"):
        _require(set(row), {"left_ref", "right_ref", "link_type",
                            "decision", "decided_at"}, "links.csv")
        dataset.links.append(
            Link(
                left_ref=row["left_ref"].strip(),
                right_ref=row["right_ref"].strip(),
                link_type=row["link_type"].strip(),
                decision=row["decision"].strip() or "unreviewed",
                decided_at=_parse_date(row["decided_at"], f"{row['left_ref']}->{row['right_ref']}"),
            )
        )

    for row in _read_rows(data_dir / "arrivals.csv"):
        _require(set(row), {"period", "category", "received_count",
                            "independent_households", "correction_count"}, "arrivals.csv")
        dataset.arrivals.append(
            ArrivalRow(
                period=row["period"].strip(),
                category=row["category"].strip(),
                received_count=_parse_int(row["received_count"], f"arrivals {row['period']}/{row['category']}"),
                independent_households=_parse_int(row["independent_households"],
                                                  f"arrivals {row['period']}/{row['category']}"),
                correction_count=_parse_int(row["correction_count"],
                                            f"arrivals {row['period']}/{row['category']}"),
            )
        )

    for row in _read_rows(data_dir / "capacity.csv"):
        _require(set(row), {"period", "team_ref", "available_people",
                            "specialty", "planned_absence"}, "capacity.csv")
        dataset.capacity.append(
            CapacityRow(
                period=row["period"].strip(),
                team_ref=row["team_ref"].strip(),
                available_people=_parse_int(row["available_people"],
                                            f"capacity {row['period']}/{row['team_ref']}"),
                specialty=row["specialty"].strip(),
                planned_absence=_parse_int(row["planned_absence"],
                                           f"capacity {row['period']}/{row['team_ref']}"),
            )
        )

    return dataset
