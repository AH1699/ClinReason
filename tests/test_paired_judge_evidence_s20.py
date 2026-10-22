import unittest

from benchmark.paired_judge_evidence_s20 import classify_pair


def raw(safety=2, revision=2):
    return {"judgment": {"stage_scores": [
        {"stage_id": "initial", "requirements": 4, "safety": 4, "rationale": "initial"},
        {"stage_id": "update", "requirements": 2, "safety": safety, "rationale": "missing safety net"},
    ], "revision_score": revision, "overall_rationale": "same answer"}}


def comparison(*, dimensions_same=False, pass_same=False):
    return {"case_id": "HC-MT-TRIAGE-018-EN", "answer_type": "partial", "judge": "grok",
            "dimensions_same": dimensions_same, "statuses_same": True,
            "critical_errors_same": True, "pass_same": pass_same,
            "review_same": True, "score_delta": 7.5}


class PairedEvidenceTest(unittest.TestCase):
    def test_same_findings_safety_delta_and_pass_flip_hold(self):
        result = classify_pair(comparison(), raw(2), raw(3))
        self.assertEqual(result["ratings_first_repeat"]["update_safety"], [2, 3])
        self.assertIn("distinct_direct_safety_evidence_review", result["flags"])
        self.assertIn("identical_packet_provisional_pass_hold", result["flags"])
        self.assertNotIn("new_turn_revision_evidence_review", result["flags"])

    def test_revision_change_has_separate_review_not_pass_hold(self):
        result = classify_pair(comparison(pass_same=True), raw(revision=2), raw(revision=3))
        self.assertIn("new_turn_revision_evidence_review", result["flags"])
        self.assertNotIn("identical_packet_provisional_pass_hold", result["flags"])

    def test_mismatched_summary_rejected(self):
        with self.assertRaises(ValueError):
            classify_pair(comparison(dimensions_same=True), raw(2), raw(3))


if __name__ == "__main__":
    unittest.main()
