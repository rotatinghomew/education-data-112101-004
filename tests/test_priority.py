"""优先级评分口径测试：缺资料不降级、影响范围不重复计数。"""

import unittest
from datetime import date

from analysis.config import Config, WAIT_EXTERNAL, WAIT_INTERNAL
from analysis.links import HouseholdCluster
from analysis.models import Complaint
from analysis.priority import build_priority_rows
from analysis.timeline import CaseState


def _state(ref: str, *, impact: str = "medium", stage: str = "assigned",
           owner: str = WAIT_INTERNAL, team: str = "T-1",
           age: int = 5, internal_age: int = 5) -> CaseState:
    complaint = Complaint(ref, f"H-{ref}", "M-1", "refund", impact,
                          date(2026, 2, 1), f"S-{ref}")
    state = CaseState(complaint=complaint, ordered_events=[], stage=stage,
                      wait_owner=owner, current_team=team,
                      age_days=age, internal_wait_age_days=internal_age)
    return state


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_unknown_evidence_never_downgrades_below_floor(self):
        states = {"C-1": _state("C-1")}
        clusters = {"C-1": HouseholdCluster("C-1", ["C-1"], ["H-1"], [], 1, 1)}
        rows = build_priority_rows(
            states, clusters,
            {"C-1": {"evidence_state": "unknown"}}, self.config,
        )
        unknown_row = rows[0]
        self.assertGreaterEqual(unknown_row.factor_readiness,
                                self.config.unknown_factor_floor)
        self.assertIn("evidence_unknown_not_downgraded", unknown_row.caution_flags)

        rows_missing = build_priority_rows(
            states, clusters,
            {"C-1": {"evidence_state": "missing"}}, self.config,
        )
        self.assertGreaterEqual(rows_missing[0].factor_readiness,
                                self.config.unknown_factor_floor)

    def test_unknown_impact_uses_conservative_factor(self):
        states = {"C-3": _state("C-3", impact="unknown")}
        clusters = {"C-3": HouseholdCluster("C-3", ["C-3"], ["H-3"], [], 1, 1)}
        rows = build_priority_rows(
            states, clusters, {"C-3": {"evidence_state": "complete"}}, self.config,
        )
        row = rows[0]
        self.assertEqual(row.factor_impact, self.config.unknown_impact_factor)
        self.assertIn("impact_unknown_treated_conservatively", row.caution_flags)

    def test_external_wait_scores_lower_stage_but_keeps_age_visible(self):
        internal_state = _state("C-1", stage="assigned", owner=WAIT_INTERNAL)
        external_state = _state("C-2", stage="waiting_consumer",
                                owner=WAIT_EXTERNAL, internal_age=0)
        states = {"C-1": internal_state, "C-2": external_state}
        clusters = {
            ref: HouseholdCluster(ref, [ref], [f"H-{ref}"], [], 1, 1)
            for ref in states
        }
        evidence = {ref: {"evidence_state": "complete"} for ref in states}
        rows = {r.complaint_ref: r for r in
                build_priority_rows(states, clusters, evidence, self.config)}
        self.assertLess(rows["C-2"].factor_stage, rows["C-1"].factor_stage)
        self.assertIn("waiting_on_consumer", rows["C-2"].caution_flags)

    def test_scope_reflects_households_not_case_multiplicity(self):
        # 同一家庭 3 件重复反馈：范围因子应按 1 户处理，不放大
        states = {"C-1": _state("C-1")}
        one_household = HouseholdCluster("C-1", ["C-1", "C-2", "C-3"],
                                         ["H-1"], [], 3, 1)
        rows_single = build_priority_rows(
            states, {"C-1": one_household},
            {"C-1": {"evidence_state": "complete"}}, self.config,
        )
        three_households = HouseholdCluster("C-1", ["C-1", "C-2", "C-3"],
                                            ["H-1", "H-2", "H-3"], [], 3, 3)
        rows_multi = build_priority_rows(
            states, {"C-1": three_households},
            {"C-1": {"evidence_state": "complete"}}, self.config,
        )
        self.assertLess(rows_single[0].factor_scope, rows_multi[0].factor_scope)
        # 单户簇的范围因子等于基线值
        self.assertEqual(rows_single[0].factor_scope, 0.4)

    def test_ranking_is_deterministic_and_banded(self):
        states = {f"C-{i}": _state(f"C-{i}", age=i) for i in range(1, 6)}
        clusters = {
            ref: HouseholdCluster(ref, [ref], [f"H-{ref}"], [], 1, 1)
            for ref in states
        }
        evidence = {ref: {"evidence_state": "complete"} for ref in states}
        rows_a = build_priority_rows(states, clusters, evidence, self.config)
        rows_b = build_priority_rows(states, clusters, evidence, self.config)
        self.assertEqual([r.complaint_ref for r in rows_a],
                         [r.complaint_ref for r in rows_b])
        scores = [r.priority_score for r in rows_a]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(r.priority_band in {"high", "medium", "low"}
                            for r in rows_a))


if __name__ == "__main__":
    unittest.main()
