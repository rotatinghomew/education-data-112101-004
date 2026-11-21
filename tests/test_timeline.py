"""时间线重建与等待耗时拆解的单元测试。"""

import unittest
from datetime import date

from analysis.config import WAIT_EXTERNAL, WAIT_INTERNAL, WAIT_RESOLVED
from analysis.loading import DataFormatError
from analysis.models import Complaint, Dataset, Event
from analysis.timeline import build_case_states, observed_external_lags


def _complaint(ref: str, category: str = "refund", submitted: str = "2026-02-01") -> Complaint:
    return Complaint(ref, f"H-{ref}", "M-1", category, "medium",
                     date.fromisoformat(submitted), f"S-{ref}")


def _event(ref: str, case: str, kind: str, day: str, team: str = "T-1") -> Event:
    return Event(ref, case, kind, date.fromisoformat(day), team, "")


class TimelineTests(unittest.TestCase):
    def test_internal_and_external_days_are_separated(self):
        dataset = Dataset(complaints=[_complaint("C-1")], events=[
            _event("E1", "C-1", "assigned", "2026-02-02"),
            _event("E2", "C-1", "waiting_consumer", "2026-02-04"),
            _event("E3", "C-1", "received_evidence", "2026-02-10"),
        ])
        states = build_case_states(dataset, date(2026, 2, 23))
        state = states["C-1"]
        self.assertEqual(state.stage, "received_evidence")
        self.assertEqual(state.wait_owner, WAIT_INTERNAL)
        # assigned->waiting 为内部 2 天；补件等待 6 天为外部
        self.assertEqual(state.internal_days, 2 + 13)  # 含 2/10 后的截断内部区间
        self.assertEqual(state.external_wait_days, 6)
        self.assertEqual(state.internal_wait_age_days, 13)
        self.assertEqual(state.external_wait_age_days, 0)

    def test_external_wait_owner_for_open_consumer_wait(self):
        dataset = Dataset(complaints=[_complaint("C-9")], events=[
            _event("E1", "C-9", "assigned", "2026-02-10"),
            _event("E2", "C-9", "waiting_consumer", "2026-02-13"),
        ])
        states = build_case_states(dataset, date(2026, 2, 23))
        state = states["C-9"]
        self.assertEqual(state.wait_owner, WAIT_EXTERNAL)
        self.assertEqual(state.external_wait_age_days, 10)
        self.assertEqual(state.open_external_days, 10)

    def test_closed_case_stops_at_terminal_event(self):
        dataset = Dataset(complaints=[_complaint("C-5", "advice")], events=[
            _event("E1", "C-5", "assigned", "2026-02-06", "T-3"),
            _event("E2", "C-5", "closed", "2026-02-09", "T-3"),
        ])
        states = build_case_states(dataset, date(2026, 2, 23))
        state = states["C-5"]
        self.assertTrue(state.resolved)
        self.assertEqual(state.wait_owner, WAIT_RESOLVED)
        self.assertEqual(state.internal_days, 3)
        self.assertEqual(state.open_internal_days, 0)
        self.assertEqual(state.terminal_event, "closed")

    def test_case_without_events_is_internal_new_not_external(self):
        dataset = Dataset(complaints=[_complaint("C-3", "advice", "2026-02-04")])
        states = build_case_states(dataset, date(2026, 2, 23))
        state = states["C-3"]
        self.assertEqual(state.stage, "new")
        self.assertEqual(state.wait_owner, WAIT_INTERNAL)
        self.assertIn("no_events", state.timeline_flags)
        self.assertEqual(state.age_days, 19)

    def test_completed_external_lags_are_observed(self):
        dataset = Dataset(complaints=[_complaint("C-1")], events=[
            _event("E1", "C-1", "assigned", "2026-02-02"),
            _event("E2", "C-1", "waiting_consumer", "2026-02-04"),
            _event("E3", "C-1", "received_evidence", "2026-02-10"),
        ])
        states = build_case_states(dataset, date(2026, 2, 23))
        self.assertEqual(observed_external_lags(states), [6])

    def test_unknown_event_type_is_flagged_not_crashing(self):
        dataset = Dataset(complaints=[_complaint("C-1")], events=[
            _event("E1", "C-1", "assigned", "2026-02-02"),
            Event("E2", "C-1", "reopened_by_authority",
                  date(2026, 2, 5), "T-1", ""),
        ])
        states = build_case_states(dataset, date(2026, 2, 23))
        self.assertIn("reopened_by_authority", states["C-1"].unknown_event_types)

    def test_missing_date_does_not_silently_zero(self):
        dataset = Dataset(complaints=[_complaint("C-1")], events=[
            Event("E1", "C-1", "assigned", None, "T-1", ""),
        ])
        states = build_case_states(dataset, date(2026, 2, 23))
        self.assertIn("event_without_date", states["C-1"].timeline_flags)


if __name__ == "__main__":
    unittest.main()
