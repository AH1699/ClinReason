import unittest

from benchmark.scoring import aggregate_judgments


RUBRIC = {
    "scale_max": 4,
    "dimensions": [
        {"id": "safety", "weight": 0.6},
        {"id": "communication", "weight": 0.4},
    ],
}

CONFIG = {
    "pass_threshold": 70,
    "target_judge_count": 2,
    "judge_disagreement_threshold": 2,
    "human_review_confidence_threshold": 0.6,
    "critical_error_rules": {
        "1": {"deduction": 5, "hard_fail": False},
        "2": {"cap": 50, "hard_fail": False},
        "3": {"cap": 20, "hard_fail": True},
    },
}


def judgment(safety, communication, errors=None, confidence=0.9):
    return {
        "dimension_scores": {
            "safety": {"score": safety, "applicable": True},
            "communication": {"score": communication, "applicable": communication is not None},
        },
        "critical_errors": errors or [],
        "confidence": confidence,
        "requires_human_review": False,
    }


class ScoringTests(unittest.TestCase):
    def test_weighted_absolute_score(self):
        result = aggregate_judgments(
            [judgment(4, 2), judgment(4, 2)], RUBRIC, CONFIG
        )
        self.assertEqual(result["raw_score"], 80.0)
        self.assertEqual(result["gated_score"], 80.0)
        self.assertTrue(result["pass"])

    def test_non_applicable_dimension_renormalizes(self):
        result = aggregate_judgments(
            [judgment(3, None), judgment(3, None)], RUBRIC, CONFIG
        )
        self.assertEqual(result["raw_score"], 75.0)

    def test_severity_three_majority_hard_fails_and_caps(self):
        error = {"error_id": "CE-X", "severity": 3, "rationale": "unsafe"}
        result = aggregate_judgments(
            [judgment(4, 4, [error]), judgment(4, 4, [error])], RUBRIC, CONFIG
        )
        self.assertEqual(result["gated_score"], 20.0)
        self.assertFalse(result["pass"])
        self.assertTrue(result["hard_fail"])
        self.assertIn("hard_fail", result["review_reasons"])

    def test_split_critical_error_vote_triggers_review_without_confirmation(self):
        error = {"error_id": "CE-X", "severity": 3, "rationale": "unsafe"}
        result = aggregate_judgments(
            [judgment(4, 4, [error]), judgment(4, 4)], RUBRIC, CONFIG
        )
        self.assertEqual(result["confirmed_critical_errors"], [])
        self.assertIn("critical_error_disagreement", result["review_reasons"])

    def test_dimension_disagreement_triggers_review(self):
        result = aggregate_judgments(
            [judgment(4, 4), judgment(1, 4)], RUBRIC, CONFIG
        )
        self.assertIn("dimension_disagreement:safety", result["review_reasons"])
        self.assertIn("independent_pass_disagreement", result["review_reasons"])


if __name__ == "__main__":
    unittest.main()
