import sys
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from independent_evaluation import binary_kappa, temporal_split, weighted_kappa  # noqa: E402


def record(identifier: str, published: str | None, posting_family: str) -> dict:
    return {
        "observationId": identifier,
        "sourcePublishedAt": published,
        "entityResolution": {"postingFamilyId": posting_family},
    }


class IndependentEvaluationTests(unittest.TestCase):
    def test_temporal_split_excludes_unknown_and_quarantines_crossing_family(self):
        protocol = {
            "temporalSplit": {
                "timestampField": "sourcePublishedAt",
                "cutoff": "2026-07-01T00:00:00+00:00",
                "minimumTrainingCandidates": 1,
                "minimumHoldoutCandidates": 1,
            }
        }
        rows = [
            record("before", "2026-06-01T00:00:00+00:00", "stable-before"),
            record("cross-before", "2026-06-15T00:00:00+00:00", "crossing"),
            record("cross-after", "2026-07-15T00:00:00+00:00", "crossing"),
            record("after", "2026-08-01T00:00:00+00:00", "stable-after"),
            record("unknown", None, "unknown"),
        ]
        training, holdout, report = temporal_split(rows, protocol)
        self.assertEqual({row["observationId"] for row in training}, {"before", "cross-before"})
        self.assertEqual([row["observationId"] for row in holdout], ["after"])
        self.assertEqual(report["excludedUnknownTimestampRecords"], 1)
        self.assertEqual(report["crossingFamiliesQuarantined"], 1)
        self.assertEqual(report["postingFamilyLeakage"], 0)
        self.assertEqual(report["status"], "pass")

    def test_agreement_metrics_have_expected_boundaries(self):
        self.assertEqual(weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]), 1.0)
        self.assertEqual(binary_kappa([0, 1, 0, 1], [0, 1, 0, 1]), 1.0)
        self.assertLess(weighted_kappa([0, 0, 3, 3], [3, 3, 0, 0]), 0)
        self.assertLess(binary_kappa([0, 0, 1, 1], [1, 1, 0, 0]), 0)

    def test_committed_packages_are_complete_equivalent_and_blind(self):
        base = ROOT / "ml" / "eval" / "independent" / "packages"
        for kind, expected_count in (("retrieval", 400), ("classification", 200)):
            a = json.loads((base / f"{kind}-reviewer-a.json").read_text())
            b = json.loads((base / f"{kind}-reviewer-b.json").read_text())
            ids_a = [task["taskId"] for task in a["tasks"]]
            ids_b = [task["taskId"] for task in b["tasks"]]
            self.assertEqual(len(ids_a), expected_count)
            self.assertEqual(len(set(ids_a)), expected_count)
            self.assertEqual(set(ids_a), set(ids_b))
            self.assertNotEqual(ids_a, ids_b)
            self.assertEqual(a["taskSetSha256"], b["taskSetSha256"])
            rendered = json.dumps(a["tasks"])
            for forbidden in ('"employer"', '"sourceUrl"', '"observationId"', '"modelScores"'):
                self.assertNotIn(forbidden, rendered)

        retrieval = json.loads((base / "retrieval-reviewer-a.json").read_text())
        per_query = {}
        for task in retrieval["tasks"]:
            per_query[task["queryId"]] = per_query.get(task["queryId"], 0) + 1
        self.assertEqual(len(per_query), 20)
        self.assertEqual(set(per_query.values()), {20})

        readiness = json.loads((ROOT / "public" / "api" / "ml" / "independent-evaluation-readiness.json").read_text())
        self.assertEqual(readiness["temporalSplit"]["postingFamilyLeakage"], 0)
        self.assertEqual(readiness["temporalSplit"]["status"], "pass")
        self.assertFalse(readiness["eligibleForPromotionDecision"])


if __name__ == "__main__":
    unittest.main()
