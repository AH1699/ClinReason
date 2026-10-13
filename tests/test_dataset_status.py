import unittest
from pathlib import Path

from benchmark.config import load_json
from benchmark.dataset_status import summarize_dataset


class DatasetStatusTests(unittest.TestCase):
    def test_global_core_alpha_status(self):
        root = Path(__file__).resolve().parents[1]
        config = load_json(root / "config" / "benchmark.json")
        rubric = load_json(root / "config" / "rubric.json")
        result = summarize_dataset(
            root / "data" / "alpha" / "global_core_cases.jsonl",
            rubric,
            config["authoring"],
        )

        self.assertEqual(result["case_count"], 64)
        self.assertEqual(result["family_count"], 32)
        self.assertEqual(result["complete_bilingual_families"], 32)
        self.assertEqual(result["categories_by_family"]["triage"], 7)
        self.assertEqual(set(value for category, value in result["categories_by_family"].items() if category != "triage"), {5})
        self.assertEqual(len(result["review_queue"]["clinical_review_pending"]), 64)
        self.assertEqual(len(result["review_queue"]["language_review_pending"]), 32)
        self.assertEqual(result["review_queue"]["source_review_pending"], [])
        self.assertTrue(result["development_validation"]["valid"])


if __name__ == "__main__":
    unittest.main()
