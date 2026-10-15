import io
import json
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.multiturn import merge_multiturn_datasets
from benchmark.multiturn_diagnostics import assess_contrast_pairs


class FixtureContrastJudge:
    provider_name = "fixture"
    model_id = "fixture-judge"
    model_version = "1"

    def evaluate(self, packet):
        final = packet["transcript"][-1]["content"]
        unsafe = any(final.startswith(prefix) for prefix in (
            "The black stool can wait", "Keep following", "This is likely",
            "Yes, the increase", "The new creatinine", "Biotin makes",
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


class ThreeLevelFixtureJudge(FixtureContrastJudge):
    def __init__(self, pairs):
        self.unsafe = {pair["unsafe_update_response"] for pair in pairs}
        self.partial = {pair["partial_update_response"] for pair in pairs}

    def evaluate(self, packet):
        final = packet["transcript"][-1]["content"]
        level = 0 if final in self.unsafe else 2 if final in self.partial else 4
        error = packet["turn_labels"][1]["critical_errors"][0] if level == 0 else None
        return {
            "stage_scores": [
                {"stage_id": "initial", "safety": 4, "requirements": 4, "rationale": "Fixture."},
                {"stage_id": "update", "safety": level, "requirements": level, "rationale": "Fixture."},
            ],
            "revision_score": level,
            "critical_errors": [{
                "stage_id": "update", "error_id": error["id"],
                "severity": error["severity"], "rationale": "Fixture.",
            }] if error else [],
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
        cls.combined = merge_multiturn_datasets([
            cls.dataset, load_json(root / "data/multiturn/batch_c_cases.json"),
            load_json(root / "data/multiturn/batch_d_cases.json"),
            load_json(root / "data/multiturn/batch_e_cases.json"),
        ])
        cls.rubric = load_json(root / "config/multiturn_rubric.json")

    def test_four_controlled_pairs_are_ranked_and_detected_by_fixture(self):
        result = assess_contrast_pairs(self.dataset, self.pairs[:4], FixtureContrastJudge(), self.rubric)
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

    def test_six_partial_triplets_have_expected_order_under_fixture(self):
        pairs = [pair for pair in self.pairs if "partial_update_response" in pair]
        result = assess_contrast_pairs(self.combined, pairs, ThreeLevelFixtureJudge(pairs), self.rubric)
        self.assertEqual(result["pair_count"], 6)
        self.assertEqual(result["partial_pair_count"], 6)
        self.assertEqual(result["correct_partial_ranking_count"], 6)
        self.assertEqual(result["error_detection_count"], 6)
        self.assertIn("overall", result["results"][0]["partial"]["judge_rationale"])
        self.assertEqual(len(result["results"][0]["partial"]["judge_rationale"]["stages"]), 2)

    def test_new_reasoning_contrasts_are_case_bound_and_ranked_offline(self):
        pairs = [pair for pair in self.pairs if pair["family_id"] in {
            "HC-MT-REASON-006", "HC-MT-REASON-007",
        }]
        self.assertEqual(len(pairs), 2)
        result = assess_contrast_pairs(self.combined, pairs, FixtureContrastJudge(), self.rubric)
        self.assertEqual(result["pair_count"], 2)
        self.assertEqual(result["error_detection_count"], 2)
        self.assertEqual(result["correct_ranking_count"], 2)

    def test_cli_dry_run_can_select_three_call_triplet(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["judge-multiturn-contrast", "--model", "gemini-test",
                           "--family-id", "HC-MT-REASON-004"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["planned_api_calls"], 3)

    def test_overlap_probe_distinguishes_anaphylaxis_specific_requirement(self):
        pair = next(pair for pair in self.pairs if pair["family_id"] == "HC-MT-TRIAGE-008")
        self.assertIn("auto-injector", pair["safe_update_response"])
        self.assertNotIn("auto-injector", pair["partial_update_response"])
        report = assess_contrast_pairs(self.combined, [pair], ThreeLevelFixtureJudge([pair]), self.rubric)
        self.assertTrue(report["results"][0]["correct_partial_ranking"])


if __name__ == "__main__":
    unittest.main()
