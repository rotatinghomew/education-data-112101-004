"""关联反馈与独立家庭去重。

口径（见 docs/methodology.md）：

* 只有 ``decision=confirmed`` 的 ``same_household`` 关联才参与
  并查集合并；complaints 自带的 ``household_ref`` 也作为同户
  事实参与合并（同户编号天然表示同一家庭）。
* ``similar_phrase`` 或任何未复核（unreviewed）关联**不自动
  合并**，只进入复核队列，避免把措辞相似的重复反馈放大或错误
  并案。
* 影响范围以簇内未结个案数/独立家庭数表达；重复反馈说明影响
  面，却不会把独立家庭或未解决案件重复计数。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Dataset


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self._parent.setdefault(item, item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, left: str, right: str) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left != root_right:
            # 取较小编号作为簇根，保证输出稳定
            if root_left < root_right:
                self._parent[root_right] = root_left
            else:
                self._parent[root_left] = root_right


@dataclass
class HouseholdCluster:
    cluster_id: str
    complaint_refs: list[str] = field(default_factory=list)
    household_refs: list[str] = field(default_factory=list)
    confirmed_links: list[str] = field(default_factory=list)
    open_complaint_count: int = 0
    open_household_count: int = 0


@dataclass
class LinkReviewItem:
    left_ref: str
    right_ref: str
    link_type: str
    decision: str
    reason: str


def build_clusters(dataset: Dataset, open_refs: set[str]) -> tuple[
    dict[str, HouseholdCluster], list[LinkReviewItem]
]:
    uf = _UnionFind()
    review_queue: list[LinkReviewItem] = []
    known_refs = {c.ref for c in dataset.complaints}

    # 1) household_ref 作为同户事实
    household_members: dict[str, list[str]] = {}
    for complaint in dataset.complaints:
        uf.find(complaint.ref)
        if complaint.household_ref:
            household_members.setdefault(complaint.household_ref, []).append(complaint.ref)
    for members in household_members.values():
        for other in members[1:]:
            uf.union(members[0], other)

    # 2) 已确认的关联
    confirmed: list[str] = []
    for link in dataset.links:
        if link.left_ref not in known_refs or link.right_ref not in known_refs:
            review_queue.append(
                LinkReviewItem(
                    link.left_ref, link.right_ref, link.link_type, link.decision,
                    reason="link_references_unknown_complaint",
                )
            )
            continue
        if link.decision == "confirmed" and link.link_type == "same_household":
            uf.union(link.left_ref, link.right_ref)
            confirmed.append(f"{link.left_ref}~{link.right_ref}")
        else:
            reason = (
                "unreviewed_link"
                if link.decision != "confirmed"
                else "confirmed_non_household_link_kept_separate"
            )
            review_queue.append(
                LinkReviewItem(
                    link.left_ref, link.right_ref, link.link_type, link.decision, reason
                )
            )

    # 3) 汇总簇
    grouped: dict[str, list[str]] = {}
    for complaint in dataset.complaints:
        grouped.setdefault(uf.find(complaint.ref), []).append(complaint.ref)

    household_lookup = {c.ref: c.household_ref for c in dataset.complaints}
    clusters: dict[str, HouseholdCluster] = {}
    for root, refs in sorted(grouped.items()):
        refs_sorted = sorted(refs)
        open_refs_in_cluster = [r for r in refs_sorted if r in open_refs]
        open_households = {
            household_lookup[r] for r in open_refs_in_cluster if household_lookup[r]
        }
        cluster = HouseholdCluster(
            cluster_id=root,
            complaint_refs=refs_sorted,
            household_refs=sorted({household_lookup[r] for r in refs_sorted
                                   if household_lookup[r]}),
            confirmed_links=[c for c in confirmed
                             if any(c.startswith(r + "~") or c.endswith("~" + r)
                                    for r in refs_sorted)],
            open_complaint_count=len(open_refs_in_cluster),
            open_household_count=len(open_households),
        )
        for ref in refs_sorted:
            clusters[ref] = cluster
    return clusters, review_queue
