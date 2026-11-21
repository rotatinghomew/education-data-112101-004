"""端到端可重跑测试：对合成数据跑完整流程并核对关键不变量。"""

import csv
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from analysis.cli import run
from analysis.config import Config

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class PipelineEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="complaint-analysis-"))
        self.out_a = self.tmp / "out-a"
        self.out_b = self.tmp / "out-b"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pipeline_runs_and_is_byte_deterministic(self):
        run(DATA, self.out_a, date(2026, 2, 23))
        run(DATA, self.out_b, date(2026, 2, 23))
        files = sorted(p.name for p in self.out_a.iterdir())
        self.assertIn("summary.md", files)
        self.assertIn("recommendation_audit.json", files)
        for name in files:
            self.assertEqual(
                (self.out_a / name).read_bytes(),
                (self.out_b / name).read_bytes(),
                f"{name} 在相同输入下重跑结果不一致",
            )

    def test_open_case_invariants(self):
        run(DATA, self.out_a, date(2026, 2, 23))
        states = _read_csv(self.out_a / "case_states.csv")
        open_states = [r for r in states if r["resolved"] == "False"]
        self.assertEqual(len(open_states), 14)
        internal = [r for r in open_states if r["wait_owner"] == "internal"]
        external = [r for r in open_states if r["wait_owner"] == "external"]
        self.assertEqual(len(internal), 9)
        self.assertEqual(len(external), 5)
        # 外部等待个案不应计入内部等待年龄
        for row in external:
            self.assertEqual(row["internal_wait_age_days"], "0")
            self.assertGreater(int(row["external_wait_age_days"]), 0)
        # C-3 无事件：保持内部 new，而不是被误判为外部等待或低风险
        c3 = next(r for r in states if r["complaint_ref"] == "C-3")
        self.assertEqual(c3["stage"], "new")
        self.assertEqual(c3["wait_owner"], "internal")
        self.assertIn("no_events", c3["timeline_flags"])

    def test_backlog_households_are_deduped(self):
        run(DATA, self.out_a, date(2026, 2, 23))
        backlog = _read_csv(self.out_a / "current_backlog.csv")
        totals = {
            r["category"]: (
                int(r["internal_open_cases"]) + int(r["external_open_cases"]),
                int(r["open_independent_households"]),
            )
            for r in backlog
        }
        # 未结 14 件分布在 refund/renewal/advice
        self.assertEqual(sum(v[0] for v in totals.values()), 14)
        # 独立家庭数不超过未结件数（去重生效）
        for category, (cases, households) in totals.items():
            self.assertLessEqual(households, cases, category)

    def test_quality_flags_surface_known_gaps(self):
        run(DATA, self.out_a, date(2026, 2, 23))
        flags = _read_csv(self.out_a / "data_quality_flags.csv")
        codes = {r["flag_code"] for r in flags}
        self.assertIn("arrival_category_missing", codes)
        self.assertIn("team_missing_from_capacity_schedule", codes)
        self.assertIn("specialty_label_mismatch", codes)
        self.assertIn("censored_segments_only", codes)

    def test_audit_json_links_recommendation_to_facts(self):
        run(DATA, self.out_a, date(2026, 2, 23))
        payload = json.loads(
            (self.out_a / "recommendation_audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["as_of"], "2026-02-23")
        categories = {a["category"] for a in payload["audits"]}
        self.assertEqual(categories, {"refund", "renewal", "advice"})
        for audit in payload["audits"]:
            facts = audit["trigger_facts"]
            self.assertIn("arrival_history", facts)
            self.assertIn("current_backlog", facts)
            self.assertIn("processing_observation", facts)
            self.assertIn("capacity_schedule", facts)
            self.assertIn("external_lag_assumption_days", facts)

    def test_projection_covers_configured_cycles_and_scenarios(self):
        run(DATA, self.out_a, date(2026, 2, 23), Config(cycles=3))
        projection = _read_csv(self.out_a / "backlog_projection.csv")
        periods = {r["period"] for r in projection}
        self.assertEqual(len(periods), 3)
        for category in {r["category"] for r in projection}:
            for period in periods:
                scenarios = {
                    r["scenario"] for r in projection
                    if r["category"] == category and r["period"] == period
                }
                self.assertEqual(scenarios, {"pessimistic", "central", "optimistic"})

    def test_pessimistic_backlog_never_below_optimistic(self):
        run(DATA, self.out_a, date(2026, 2, 23))
        projection = _read_csv(self.out_a / "backlog_projection.csv")
        for period in {r["period"] for r in projection}:
            for category in {r["category"] for r in projection}:
                rows = [r for r in projection
                        if r["period"] == period and r["category"] == category]
                by_scenario = {r["scenario"]: int(r["ending_internal_backlog"])
                               for r in rows}
                self.assertGreaterEqual(
                    by_scenario["pessimistic"], by_scenario["optimistic"]
                )


if __name__ == "__main__":
    unittest.main()
