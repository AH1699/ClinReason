import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json, load_jsonl
from benchmark.judge_diagnostics import assess_contrasts
from benchmark.providers.base import JudgeProvider


class ContrastJudge(JudgeProvider):
    provider_name = "fixture"
    model_id = "fixture-judge"
    model_version = "1"

    def __init__(self, miss_error=False):
        self.miss_error = miss_error

    def evaluate(self, case, response, rubric):
        unsafe = response["text"].startswith("This is probably")
        error_id = case["critical_errors"][0]["id"]
        return {
            "dimension_scores": {
                dim["id"]: {
                    "applicable": dim["id"] in case["applicable_dimensions"],
                    "score": (0 if unsafe else 4) if dim["id"] in case["applicable_dimensions"] else None,
                }
                for dim in rubric["dimensions"]
            },
            "critical_errors": [{"error_id": error_id, "severity": 3}] if unsafe and not self.miss_error else [],
            "confidence": 1.0,
            "requires_human_review": False,
        }


class JudgeDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.cases = load_jsonl(root / "data/alpha/global_core_cases.jsonl")
        cls.rubric = load_json(root / "config/rubric.json")
        cls.scoring = load_json(root / "config/benchmark.json")["scoring"]
        cls.pairs = load_json(root / "data/alpha/judge_contrasts.json")["pairs"]

    def test_all_contrast_references_match_configured_severity_three_errors(self):
        result = assess_contrasts(self.cases, self.pairs[:1], ContrastJudge(), self.rubric, self.scoring)
        self.assertEqual(result["pair_count"], 1)
        self.assertEqual(result["error_detection_count"], 1)
        self.assertEqual(result["correct_ranking_count"], 1)
        for pair in self.pairs:
            case = next(case for case in self.cases if case["id"] == pair["case_id"])
            self.assertIn((pair["expected_unsafe_error_id"], 3),
                          {(error["id"], error["severity"]) for error in case["critical_errors"]})

    def test_missing_error_is_reported_not_hidden_by_score_ranking(self):
        result = assess_contrasts(self.cases, self.pairs[:1], ContrastJudge(miss_error=True),
                                  self.rubric, self.scoring)
        self.assertEqual(result["error_detection_count"], 0)
        self.assertEqual(result["correct_ranking_count"], 1)

    def test_cli_dry_run_makes_no_api_calls(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["judge-contrast-gemini", "--model", "test-model", "--limit", "4"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["planned_api_calls"], 8)


if __name__ == "__main__":
    unittest.main()
