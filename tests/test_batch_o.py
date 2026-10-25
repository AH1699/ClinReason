from copy import deepcopy
from pathlib import Path
import unittest

from benchmark.config import load_json
from scripts import audit_batch_o as batch


ROOT = Path(__file__).resolve().parents[1]


class StandaloneBatchOTests(unittest.TestCase):
    def setUp(self):
        self.data = {name: load_json(ROOT / path) for name, path in batch.FILES.items()}

    def validate(self):
        return batch.validate(self.data["cases"], self.data["anchors"],
                              self.data["controls"], self.data["provenance"])

    def test_complete_standalone_pack_retains_separate_counts(self):
        result = batch.audit(ROOT)
        self.assertEqual((result["standalone_families"], result["language_variants"],
                          result["criterion_positions"], result["default_portfolio_additions"]),
                         (2, 4, 12, 0))
        self.assertEqual(len(set(result["packet_hashes"].values())), 12)
        self.assertEqual((result["api_calls"], result["numeric_scores"]), (0, 0))

    def test_changed_prompt_invalidates_the_attached_labels(self):
        self.data["cases"]["families"][0]["variants"]["en"]["turns"][0]["user"] += " New fact."
        with self.assertRaises(ValueError):
            self.validate()

    def test_a_missing_source_position_is_not_complete_mapping(self):
        self.data["provenance"]["records"][0]["requirement_support"].pop()
        with self.assertRaises(ValueError):
            self.validate()

    def test_a_source_outside_the_declared_case_sources_is_rejected(self):
        self.data["provenance"]["records"][0]["requirement_support"][0]["guidance_url"] = "https://example.org/unsupported"
        with self.assertRaises(ValueError):
            self.validate()

    def test_duplicate_language_does_not_replace_a_missing_variant(self):
        self.data["controls"]["probes"][1] = deepcopy(self.data["controls"]["probes"][0])
        with self.assertRaises(ValueError):
            self.validate()

    def test_unrelated_omission_cannot_silently_change_the_control(self):
        self.data["controls"]["probes"][0]["construction"]["partial_omitted_requirement_index"] = 1
        with self.assertRaises(ValueError):
            self.validate()

    def test_unsafe_profile_cannot_claim_an_invented_error(self):
        self.data["controls"]["probes"][0]["expected_unsafe_error_id"] = "CE-NOT-IN-CASE"
        with self.assertRaises(ValueError):
            self.validate()


if __name__ == "__main__":
    unittest.main()
