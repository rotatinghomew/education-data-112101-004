"""证据完整度与关联去重口径的单元测试。"""

import unittest
from datetime import date

from analysis.config import (
    EVIDENCE_COMPLETE,
    EVIDENCE_MISSING,
    EVIDENCE_PARTIAL,
    EVIDENCE_UNKNOWN,
)
from analysis.evidence import evaluate_evidence
from analysis.links import build_clusters
from analysis.models import Complaint, Dataset, EvidenceRecord, Link


def _complaint(ref: str, household: str) -> Complaint:
    return Complaint(ref, household, "M-1", "refund", "medium",
                     date(2026, 2, 1), f"S-{ref}")


class EvidenceTests(unittest.TestCase):
    def test_superseded_partial_is_replaced_by_complete(self):
        dataset = Dataset(
            complaints=[_complaint("C-1", "H-1")],
            evidence=[
                EvidenceRecord("E-1", "C-1", date(2026, 2, 1), "order", "partial", ""),
                EvidenceRecord("E-2", "C-1", date(2026, 2, 10), "payment",
                               "complete", "E-1"),
            ],
        )
        result = evaluate_evidence(dataset)["C-1"]
        self.assertEqual(result["evidence_state"], EVIDENCE_COMPLETE)
        self.assertEqual(result["effective_count"], 1)
        self.assertEqual(result["superseded_count"], 1)

    def test_unknown_completeness_is_not_treated_as_missing_or_low(self):
        dataset = Dataset(
            complaints=[_complaint("C-3", "H-2")],
            evidence=[
                EvidenceRecord("E-3", "C-3", date(2026, 2, 5), "recording",
                               "unknown", ""),
            ],
        )
        self.assertEqual(
            evaluate_evidence(dataset)["C-3"]["evidence_state"], EVIDENCE_UNKNOWN
        )

    def test_no_evidence_is_missing(self):
        dataset = Dataset(complaints=[_complaint("C-2", "H-1")])
        self.assertEqual(
            evaluate_evidence(dataset)["C-2"]["evidence_state"], EVIDENCE_MISSING
        )

    def test_partial_only(self):
        dataset = Dataset(
            complaints=[_complaint("C-6", "H-7")],
            evidence=[
                EvidenceRecord("E-6", "C-6", date(2026, 2, 9), "order", "partial", ""),
            ],
        )
        self.assertEqual(
            evaluate_evidence(dataset)["C-6"]["evidence_state"], EVIDENCE_PARTIAL
        )


class ClusterTests(unittest.TestCase):
    def _dataset(self) -> Dataset:
        return Dataset(
            complaints=[
                _complaint("C-1", "H-1"),
                _complaint("C-2", "H-1"),
                _complaint("C-3", "H-2"),
                _complaint("C-4", "H-5"),
                _complaint("C-5", "H-6"),
            ],
            links=[
                Link("C-1", "C-2", "same_household", "confirmed", date(2026, 2, 12)),
                Link("C-2", "C-3", "similar_phrase", "unreviewed", None),
                Link("C-5", "C-4", "same_household", "confirmed", date(2026, 2, 10)),
            ],
        )

    def test_confirmed_links_and_household_refs_merge_but_unreviewed_do_not(self):
        dataset = self._dataset()
        clusters, review = build_clusters(dataset, {"C-1", "C-2", "C-3", "C-4", "C-5"})
        # C-1/C-2 同户；C-3 虽与 C-2 有未复核相似措辞，也不得自动并入
        self.assertEqual(clusters["C-1"].cluster_id, clusters["C-2"].cluster_id)
        self.assertNotEqual(clusters["C-2"].cluster_id, clusters["C-3"].cluster_id)
        # confirmed same_household 合并 C-4/C-5
        self.assertEqual(clusters["C-4"].cluster_id, clusters["C-5"].cluster_id)
        self.assertEqual(len(review), 1)
        self.assertEqual(review[0].reason, "unreviewed_link")

    def test_open_households_are_not_double_counted(self):
        dataset = self._dataset()
        clusters, _ = build_clusters(dataset, {"C-1", "C-2", "C-3"})
        cluster_c1 = clusters["C-1"]
        # 簇内两件未结个案但只属于 1 个独立家庭
        self.assertEqual(cluster_c1.open_complaint_count, 2)
        self.assertEqual(cluster_c1.open_household_count, 1)

    def test_unknown_link_target_goes_to_review(self):
        dataset = Dataset(
            complaints=[_complaint("C-1", "H-1")],
            links=[Link("C-1", "C-999", "similar_phrase", "unreviewed", None)],
        )
        _, review = build_clusters(dataset, {"C-1"})
        self.assertEqual(review[0].reason, "link_references_unknown_complaint")


if __name__ == "__main__":
    unittest.main()
