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

        self.assertEqual(result["case_count"], 24)
        self.assertEqual(result["family_count"], 12)
        self.assertEqual(result["complete_bilingual_families"], 12)
        self.assertEqual(set(result["categories_by_family"].values()), {2})
        self.assertEqual(len(result["review_queue"]["clinical_review_pending"]), 24)
        self.assertEqual(len(result["review_queue"]["language_review_pending"]), 12)
        self.assertEqual(result["review_queue"]["source_review_pending"], [])
        self.assertTrue(result["development_validation"]["valid"])


if __name__ == "__main__":
    unittest.main()
