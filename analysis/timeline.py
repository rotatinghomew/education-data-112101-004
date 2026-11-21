"""个案时间线重建与等待耗时拆解。

核心口径（写入 docs/methodology.md）：

* ``assigned -> waiting_consumer`` 等区间是团队在办案，计入
  **内部处理天数**（active_handling_days）；
* ``waiting_consumer -> received_evidence`` 是等消费者补件，
  计入 **外部等待天数**（external_wait_days），不占用排班产能；
* 已结案个案只统计到终结事件；未结案个案统计到分析基准日，
  其未结束区间属于右截断（right-censored），会在产能估计中
  以放大系数处理，而不是当作完整办案时长。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .config import (
    EXTERNAL_WAIT_EVENT,
    KNOWN_EVENTS,
    TERMINAL_EVENTS,
    WAIT_EXTERNAL,
    WAIT_INTERNAL,
    WAIT_RESOLVED,
)
from .models import Complaint, Dataset, Event


@dataclass
class Segment:
    """两个事件之间（或到基准日）的一段时间。"""

    start_date: date
    end_date: date
    days: float
    kind: str  # internal | external
    from_event: str
    to_event: str
    censored: bool
    team_ref: str


@dataclass
class CaseState:
    complaint: Complaint
    ordered_events: list[Event]
    segments: list[Segment] = field(default_factory=list)
    stage: str = "new"
    wait_owner: str = WAIT_INTERNAL
    current_team: str = ""
    resolved: bool = False
    terminal_event: str = ""
    internal_days: float = 0.0
    external_wait_days: float = 0.0
    open_internal_days: float = 0.0
    open_external_days: float = 0.0
    age_days: int = 0
    internal_wait_age_days: int = 0
    external_wait_age_days: int = 0
    last_event_date: date | None = None
    unknown_event_types: list[str] = field(default_factory=list)
    timeline_flags: list[str] = field(default_factory=list)


def _segment_kind(event_type: str) -> str:
    return "external" if event_type == EXTERNAL_WAIT_EVENT else "internal"


def build_case_states(dataset: Dataset, as_of: date) -> dict[str, CaseState]:
    """按基准日重建每个个案的当前阶段与耗时拆解。"""
    events_by_case: dict[str, list[Event]] = {}
    for event in dataset.events:
        events_by_case.setdefault(event.complaint_ref, []).append(event)

    states: dict[str, CaseState] = {}
    for complaint in dataset.complaints:
        events = sorted(
            events_by_case.get(complaint.ref, []),
            key=lambda e: (e.event_at or date.max, e.event_ref),
        )
        state = CaseState(complaint=complaint, ordered_events=events)
        valid_events = [e for e in events if e.event_at is not None]
        if len(valid_events) != len(events):
            state.timeline_flags.append("event_without_date")

        if not valid_events:
            # 没有任何处置记录：保持 new，年龄从提交日起算，
            # 归属内部（团队尚未接手，不能视为外部等待）。
            state.stage = "new"
            state.wait_owner = WAIT_INTERNAL
            state.timeline_flags.append("no_events")
        else:
            _reconstruct(state, valid_events, as_of)

        if complaint.submitted_at is not None:
            state.age_days = max(0, (as_of - complaint.submitted_at).days)
        else:
            state.timeline_flags.append("missing_submitted_at")

        states[complaint.ref] = state

    # 事件引用了不存在的个案
    known = {c.ref for c in dataset.complaints}
    for ref in events_by_case:
        if ref not in known:
            states.setdefault(
                ref,
                CaseState(
                    complaint=Complaint(ref, "", "", "unknown", "unknown", None, ""),
                    ordered_events=[],
                    timeline_flags=["orphan_event"],
                ),
            )
    return states


def _reconstruct(state: CaseState, events: list[Event], as_of: date) -> None:
    terminal_seen = False
    for index, event in enumerate(events):
        if event.event_type not in KNOWN_EVENTS:
            state.unknown_event_types.append(event.event_type)
            state.timeline_flags.append(f"unknown_event_type:{event.event_type}")
        if event.event_at > as_of:
            state.timeline_flags.append("events_after_as_of_excluded")
            break

        state.last_event_date = event.event_at
        if event.team_ref:
            state.current_team = event.team_ref

        if index + 1 < len(events):
            nxt = events[index + 1]
            if nxt.event_at <= as_of:
                end = nxt.event_at
                censored = False
                to_event = nxt.event_type
            else:
                # 下一事件在基准日之后：区间截断到基准日
                end = as_of
                censored = True
                to_event = f"open_after_{event.event_type}"
        else:
            end = as_of
            censored = True
            to_event = f"open_after_{event.event_type}"

        days = max(0, (end - event.event_at).days)
        kind = _segment_kind(event.event_type)
        state.segments.append(
            Segment(
                start_date=event.event_at,
                end_date=end,
                days=days,
                kind=kind,
                from_event=event.event_type,
                to_event=to_event,
                censored=censored,
                team_ref=event.team_ref,
            )
        )

        if event.event_type in TERMINAL_EVENTS:
            terminal_seen = True
            state.resolved = True
            state.terminal_event = event.event_type
            state.stage = "resolved"
            state.wait_owner = WAIT_RESOLVED
            # 终结事件之后若还有记录，保留在时间线里但不再生成等待区间
            break

    if not terminal_seen:
        last = events[-1]
        state.stage = last.event_type
        state.wait_owner = (
            WAIT_EXTERNAL if last.event_type == EXTERNAL_WAIT_EVENT else WAIT_INTERNAL
        )

    # 耗时汇总
    for segment in state.segments:
        if state.resolved and segment.censored:
            continue
        if segment.kind == "external":
            state.external_wait_days += segment.days
            if segment.censored:
                state.open_external_days += segment.days
        else:
            state.internal_days += segment.days
            if segment.censored:
                state.open_internal_days += segment.days

    if not state.resolved:
        # 等待年龄：当前未结束区间已持续多久，用于区分
        # “等内部判断”与“等外部资料”的积压年龄
        if state.segments and state.segments[-1].censored:
            current = state.segments[-1]
            if current.kind == "external":
                state.external_wait_age_days = int(current.days)
            else:
                state.internal_wait_age_days = int(current.days)


def observed_external_lags(states: dict[str, CaseState]) -> list[float]:
    """已完成的补件循环时长（waiting_consumer -> received_evidence）。"""
    lags: list[float] = []
    for state in states.values():
        for segment in state.segments:
            if segment.kind == "external" and not segment.censored:
                lags.append(segment.days)
    return lags
