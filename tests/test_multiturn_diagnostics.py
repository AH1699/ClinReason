import io
import json
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.multiturn_diagnostics import assess_contrast_pairs


class FixtureContrastJudge:
    provider_name = "fixture"
    model_id = "fixture-judge"
    model_version = "1"

    def evaluate(self, packet):
        final = packet["transcript"][-1]["content"]
        unsafe = any(final.startswith(prefix) for prefix in (
            "The black stool can wait", "Keep following", "This is likely",
            "Yes, the increase",
        ))
        configured = packet["turn_labels"][1]["critical_errors"][0] if unsafe else None
        return {
            "stage_scores": [
                {"stage_id": "initial", "safety": 4, "requirements": 4, "rationale": "Fixture."},
                {"stage_id": "update", "safety": 0 if unsafe else 4,
                 "requirements": 0 if unsafe else 4, "rationale": "Fixture."},
            ],
            "revision_score": 0 if unsafe else 4,
            "critical_errors": [{
                "stage_id": "update", "error_id": configured["id"],
                "severity": configured["severity"], "rationale": "Fixture.",
            }] if unsafe else [],
            "confidence": 1.0,
            "requires_human_review": False,
            "overall_rationale": "Fixture only.",
        }


class MultiturnDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.dataset = load_json(root / "data/multiturn/pilot_cases.json")
        cls.pairs = load_json(root / "data/multiturn/contrast_transcripts.json")["pairs"]
        cls.rubric = load_json(root / "config/multiturn_rubric.json")

    def test_four_controlled_pairs_are_ranked_and_detected_by_fixture(self):
        result = assess_contrast_pairs(self.dataset, self.pairs, FixtureContrastJudge(), self.rubric)
        self.assertEqual(result["pair_count"], 4)
        self.assertEqual(result["error_detection_count"], 4)
        self.assertEqual(result["correct_ranking_count"], 4)
        self.assertTrue(all(row["safe"]["gated_score"] > row["unsafe"]["gated_score"]
                            for row in result["results"]))

    def test_wrong_expected_error_is_rejected(self):
        pairs = deepcopy(self.pairs[:1])
        pairs[0]["expected_unsafe_error_id"] = "NOT_CONFIGURED"
        with self.assertRaises(ValueError):
            assess_contrast_pairs(self.dataset, pairs, FixtureContrastJudge(), self.rubric)

    def test_cli_dry_run_plans_two_judge_calls_per_pair(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["judge-multiturn-contrast", "--model", "gemini-test", "--limit", "4"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["planned_api_calls"], 8)


if __name__ == "__main__":
    unittest.main()
