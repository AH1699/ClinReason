import unittest
from pathlib import Path

from benchmark.config import load_json
from benchmark.multiturn import validate_multiturn_dataset


ROOT = Path(__file__).resolve().parents[1]


class BatchKSourceTests(unittest.TestCase):
    def test_exam_mechanism_is_separate_from_current_answer_source(self):
        batch = load_json(ROOT / "data/multiturn/batch_k_cases.json")
        provenance = load_json(ROOT / "data/multiturn/batch_k_provenance.json")
        self.assertEqual(validate_multiturn_dataset(batch)["family_count"], 1)
        family = batch["families"][0]
        record = provenance["records"][0]
        self.assertEqual(family["family_id"], record["family_id"])
        self.assertEqual(set(family["source_refs"]), set(record["supporting_sources"]))
        self.assertEqual(len(record["requirement_support"]), 7)
        for item in record["requirement_support"]:
            self.assertIn(item["guidance_url"], family["source_refs"])
            self.assertTrue(item["basis"])
        self.assertIn("older rigid", record["outdated_source_warning"])
        self.assertEqual(provenance["split"], "public_development_not_calibration_or_gold")


if __name__ == "__main__":
    unittest.main()
