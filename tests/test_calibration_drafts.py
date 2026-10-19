import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.calibration_drafts import validate_calibration_contrasts
from benchmark.config import load_json
from benchmark.multiturn import merge_multiturn_datasets


class CalibrationDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.config = load_json(root / "config/benchmark.json")
        cls.dataset = merge_multiturn_datasets([
            load_json(root / "data/calibration/multiturn_candidates_v1.json"),
            load_json(root / "data/calibration/multiturn_candidates_batch_b.json"),
        ])
        cls.anchors = load_json(root / "data/calibration/criterion_anchors_v1.json")
        cls.contrasts = load_json(root / "data/calibration/response_contrasts_v1.json")

    def test_complete_bilingual_packet_is_provisional_and_isolated(self):
        result = validate_calibration_contrasts(self.contrasts, self.dataset, self.anchors)
        self.assertEqual((result["family_count"], result["variant_count"], result["update_response_example_count"]), (6, 12, 36))
        self.assertFalse(result["clinical_review_complete"])
        self.assertFalse(result["language_review_complete"])
        self.assertNotIn("data/calibration/multiturn_candidates_v1.json", self.config["multiturn_cases_paths"])
        self.assertNotIn("data/calibration/multiturn_candidates_batch_b.json", self.config["multiturn_cases_paths"])

    def test_stale_case_hash_is_rejected(self):
        changed = deepcopy(self.contrasts)
        changed["families"][0]["variants"]["en"]["case_content_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Stale calibration contrast"):
            validate_calibration_contrasts(changed, self.dataset, self.anchors)

    def test_wrong_unsafe_error_or_partial_index_is_rejected(self):
        changed = deepcopy(self.contrasts)
        changed["families"][0]["variants"]["zh-Hans"]["unsafe_error_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "Unknown calibration update"):
            validate_calibration_contrasts(changed, self.dataset, self.anchors)
        changed = deepcopy(self.contrasts)
        changed["families"][0]["variants"]["en"]["partial_target_requirement_index"] = 99
        with self.assertRaisesRegex(ValueError, "Invalid calibration partial-target"):
            validate_calibration_contrasts(changed, self.dataset, self.anchors)

    def test_missing_family_and_duplicated_response_are_rejected(self):
        changed = deepcopy(self.contrasts)
        changed["families"].pop()
        with self.assertRaisesRegex(ValueError, "do not cover the same families"):
            validate_calibration_contrasts(changed, self.dataset, self.anchors)
        changed = deepcopy(self.contrasts)
        changed["families"][0]["variants"]["en"]["partial_update_response"] = changed["families"][0]["variants"]["en"]["strong_update_response"]
        with self.assertRaisesRegex(ValueError, "nonempty and distinct"):
            validate_calibration_contrasts(changed, self.dataset, self.anchors)

    def test_bilingual_targets_must_match(self):
        changed = deepcopy(self.contrasts)
        changed["families"][0]["variants"]["zh-Hans"]["partial_target_requirement_index"] = 1
        with self.assertRaisesRegex(ValueError, "targets differ"):
            validate_calibration_contrasts(changed, self.dataset, self.anchors)


if __name__ == "__main__":
    unittest.main()
