"""数据记录的内存表示。

金额/计数字段在源文件中以文本保存，这里只在确有数值语义的列
（到达计数、排班人数、缺勤）上做转换，其余保持文本，避免把
空字符串误解释为零。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Complaint:
    ref: str
    household_ref: str
    merchant_ref: str
    category: str
    impact_band: str
    submitted_at: date | None
    source_ref: str


@dataclass(frozen=True)
class Event:
    event_ref: str
    complaint_ref: str
    event_type: str
    event_at: date | None
    team_ref: str
    detail: str


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_ref: str
    complaint_ref: str
    received_at: date | None
    evidence_type: str
    completeness: str
    supersedes: str


@dataclass(frozen=True)
class Link:
    left_ref: str
    right_ref: str
    link_type: str
    decision: str
    decided_at: date | None


@dataclass(frozen=True)
class ArrivalRow:
    period: str
    category: str
    received_count: int
    independent_households: int
    correction_count: int


@dataclass(frozen=True)
class CapacityRow:
    period: str
    team_ref: str
    available_people: int
    specialty: str
    planned_absence: int


@dataclass
class Dataset:
    complaints: list[Complaint] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    arrivals: list[ArrivalRow] = field(default_factory=list)
    capacity: list[CapacityRow] = field(default_factory=list)
