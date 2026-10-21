"""Portable fixtures for the descriptive EN/ZH authored-contrast comparison."""

import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_json
from benchmark.contrast_pair_audit import audit_contrast_pair
from benchmark.multiturn import merge_multiturn_datasets, variant_id
from benchmark.provenance import sha256_json, sha256_text


class ContrastPairAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        config = load_json(root / "config/benchmark.json")
        cls.dataset = merge_multiturn_datasets([
            load_json(root / path) for path in config["multiturn_cases_paths"]
        ])
        cls.family = next(item for item in cls.dataset["families"]
                          if item["family_id"] == "HC-MT-TRIAGE-019")
        cls.anchors = load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json")
        cls.rubric = load_json(root / "config/multiturn_rubric.json")
        cls.roster = load_json(root / "config/model_matrix.json")
        cls.instruction = (root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip()
        cls.en_probe = load_json(root / "data/multiturn/batch_g_near_miss_019_en_v1.json")
        cls.zh_probe = load_json(root / "data/multiturn/batch_g_near_miss_019_zh_v1.json")

    def _report(self, language, probe, scores):
        initial = ["met"] * 3
        statuses = {
            "safe": initial + ["met", "met", "met"],
            "partial": initial + ["met", "partial", "missed"],
            "unsafe": initial + ["met", "missed", "met"],
        }
        results = {}
        for provider, values in scores.items():
            model = next(item["model"] for item in self.roster["judges"]
                         if item["provider"] == provider)
            results[provider] = {"model_requested": model, "variants": {
                variant: {"gated_score": score, "pass": score >= 70,
                          "criterion_statuses": statuses[variant],
                          "critical_error_ids": ([probe["expected_unsafe_error_id"]]
                                                 if variant == "unsafe" else [])}
                for variant, score in values.items()
            }}
        return {
            "status": "synthetic_contrast_two_ai_judges_not_clinical_validation",
            "case_id": variant_id(self.family, language),
            "case_content_hash": probe["case_content_hash"],
            "probe_sha256": sha256_json(probe),
            "roster_sha256": sha256_json(self.roster),
            "dataset_sha256": sha256_json(self.dataset),
            "rubric_sha256": sha256_json(self.rubric),
            "criterion_anchors_sha256": sha256_json(self.anchors),
            "judge_instruction_sha256": sha256_text(self.instruction),
            "judge_calls": 6, "candidate_calls": 0, "results": results,
        }

    def _fixture(self):
        en = self._report("en", self.en_probe, {
            "gemini": {"safe": 100, "partial": 60, "unsafe": 50},
            "grok": {"safe": 100, "partial": 72.5, "unsafe": 67.5},
        })
        zh = self._report("zh-Hans", self.zh_probe, {
            "gemini": {"safe": 100, "partial": 77.5, "unsafe": 60},
            "grok": {"safe": 100, "partial": 72.5, "unsafe": 60},
        })
        return en, zh

    def _audit(self, en, zh):
        return audit_contrast_pair(en, zh, self.en_probe, self.zh_probe,
                                   self.dataset, self.anchors, self.rubric,
                                   self.roster, self.instruction)

    def test_reports_same_status_score_gap_without_rescoring(self):
        en, zh = self._fixture()
        result = self._audit(en, zh)
        self.assertEqual(result["completed_judge_calls"], 12)
        self.assertEqual(len(result["same_status_score_gaps_at_least_5"]), 3)
        gemini_partial = next(item for item in result["comparisons"]
                              if item["judge_provider"] == "gemini"
                              and item["answer_variant"] == "partial")
        self.assertEqual(gemini_partial["zh_minus_en"], 17.5)
        self.assertTrue(gemini_partial["pass_mismatch"])
        self.assertTrue(gemini_partial["same_criterion_statuses"])

    def test_rejects_changed_probe_or_instruction_hash(self):
        en, zh = self._fixture()
        changed = deepcopy(en)
        changed["probe_sha256"] = "stale"
        with self.assertRaisesRegex(ValueError, "wrong-protocol"):
            self._audit(changed, zh)
        changed = deepcopy(zh)
        changed["judge_instruction_sha256"] = "stale"
        with self.assertRaisesRegex(ValueError, "wrong-protocol"):
            self._audit(en, changed)


if __name__ == "__main__":
    unittest.main()
