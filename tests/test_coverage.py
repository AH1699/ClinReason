import json
import unittest
from pathlib import Path

from benchmark.config import load_jsonl
from benchmark.coverage import audit_coverage


class CoverageTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.cases = load_jsonl(root / "data/alpha/global_core_cases.jsonl")
        self.tags = json.loads((root / "data/alpha/coverage_tags.json").read_text(encoding="utf-8"))
        self.splits = json.loads((root / "data/alpha/family_splits.json").read_text(encoding="utf-8"))
        self.labels = json.loads((root / "data/alpha/family_labels.json").read_text(encoding="utf-8"))

    def test_current_coverage_reports_real_gaps(self):
        result = audit_coverage(self.cases, self.tags, self.splits, self.labels)
        self.assertEqual(result["family_count"], 30)
        self.assertEqual(result["prompt_count"], 60)
        self.assertEqual(result["triage_acuity"], {"emergency": 4, "timely_nonemergency": 1})
        self.assertEqual(result["missing_triage_acuity"], ["routine", "self_care"])
        self.assertEqual(result["missing_interactions"], ["multi_turn"])
        self.assertEqual(result["missing_audiences"], ["clinician"])
        self.assertEqual(result["split_counts"], {"development": 30, "calibration": 0, "hidden_gold": 0})
        self.assertIn("temporal_reassessment", result["by_reasoning_operation"])
        self.assertIn("longitudinal_values_without_provenance", result["by_complexity_tag"])

    def test_new_family_requires_explicit_tags_and_split(self):
        case = dict(self.cases[0])
        case["metadata"] = {**case["metadata"], "case_family_id": "NEW"}
        with self.assertRaises(ValueError):
            audit_coverage(self.cases + [case], self.tags, self.splits)

    def test_family_cannot_be_in_two_splits(self):
        splits = json.loads(json.dumps(self.splits))
        splits["splits"]["calibration"].append(splits["splits"]["development"][0])
        with self.assertRaises(ValueError):
            audit_coverage(self.cases, self.tags, splits)


if __name__ == "__main__":
    unittest.main()
