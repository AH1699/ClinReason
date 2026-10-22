"""No-network checks for the non-enforced S15 scoring hypothesis audit."""

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.config import load_json
from benchmark.multiturn import merge_multiturn_datasets
from benchmark.scoring_dimension_hypothesis import compare_pairs, validate_fresh_probe


ROOT = Path(__file__).resolve().parents[1]


class ScoringDimensionHypothesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_json(ROOT / "config/scoring_dimension_hypotheses_s15_v1.json")
        config = load_json(ROOT / "config/benchmark.json")
        cls.dataset = merge_multiturn_datasets([load_json(ROOT / path)
                                                for path in config["multiturn_cases_paths"]])

    def test_fresh_bilingual_probe_is_frozen_to_exact_safe_answers(self):
        result = validate_fresh_probe(ROOT, self.dataset, self.policy)
        self.assertEqual(len(result["manifest"]), 2)
        self.assertEqual({row["planned_judge_calls"] for row in result["manifest"]}, {0})
        self.assertNotEqual(result["manifest"][0]["baseline_update_sha256"],
                            result["manifest"][0]["omission_update_sha256"])

    def test_fresh_probe_rejects_an_unfrozen_extra_edit(self):
        original = load_json(ROOT / self.policy["fresh_probe_path"])
        edited = copy.deepcopy(original)
        edited["languages"][0]["base_update_segments"][0] += " Extra sentence."
        real_load = load_json

        def altered(path):
            return edited if Path(path) == ROOT / self.policy["fresh_probe_path"] else real_load(path)

        with patch("benchmark.scoring_dimension_hypothesis.load_json", side_effect=altered):
            with self.assertRaisesRegex(ValueError, "one-segment edit"):
                validate_fresh_probe(ROOT, self.dataset, self.policy)

    def test_pair_comparison_keeps_ratings_separate_and_never_rescores(self):
        spec = self.policy["cohorts"][2]
        rows = []
        for case_id in ("HC-MT-TRIAGE-020-EN", "HC-MT-TRIAGE-020-ZH-HANS"):
            for judge_id in ("gemini-judge", "grok-judge"):
                for variant, status, requirements, safety, revision, gated in (
                    ("baseline", "met", 4, 4, 4, 100),
                    ("safety_net_omission", "partial", 3, 4, 4, 95),
                ):
                    rows.append({
                        "file": f"{case_id}_{judge_id}_{variant}", "family_id": spec["family_id"],
                        "case_id": case_id, "judge_id": judge_id, "answer_id": variant,
                        "statuses": {"initial": ("met", "met", "met"),
                                     "update": ("met", "met", status)},
                        "stages": {"update": {"requirements": requirements, "safety": safety}},
                        "revision": revision, "gated": gated, "pass": True, "errors": [],
                    })
        before = copy.deepcopy(rows)
        report = compare_pairs(rows, spec)
        self.assertEqual(rows, before)
        self.assertEqual(report["observed_lowered_patterns"], {"requirements": 4})
        self.assertEqual(report["pair_count"], 4)
        rows[-1]["statuses"]["update"] = ("met", "met", "met")
        with self.assertRaisesRegex(ValueError, "predeclared"):
            compare_pairs(rows, spec)


if __name__ == "__main__":
    unittest.main()
