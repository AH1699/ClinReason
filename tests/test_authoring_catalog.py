from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import authoring_catalog as module

ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def test_counts_preserve_registration_and_language_denominators(self):
        value = module.catalog(ROOT)
        self.assertEqual(value["counts"]["registered_families"], 125)
        self.assertEqual(value["counts"]["registered_variants"], 250)
        self.assertEqual(value["counts"]["standalone_families"], 8)
        self.assertEqual(value["counts"]["standalone_variants"], 16)
        self.assertEqual(value["counts"]["distinct_public_draft_families"], 133)
        self.assertEqual(value["counts"]["additional_draft_families_to_target"], 367)
        self.assertEqual(value["counts"]["registered_by_track"],
                         {"alpha_single_turn": 32, "patient_multiturn": 51, "professional": 42})
        self.assertFalse(value["scope"]["default_registry_changed"])
        self.assertEqual(value["scope"]["new_cases_created"], 0)

    def test_entries_have_real_paths_and_no_prompt_or_answer_text(self):
        value = module.catalog(ROOT)
        for family in value["families"]:
            self.assertTrue((ROOT / family["case_path"]).is_file())
            self.assertEqual(family["languages"], ["en", "zh-Hans"])
            self.assertEqual(len(family["content_sha256"]), 64)
            self.assertFalse(family["clinical_validation"])
            self.assertNotIn("prompt", family); self.assertNotIn("reference_answer", family)

    def test_private_outside_and_absolute_paths_rejected(self):
        for path in ("work/private.json", "data/../../secret", "/tmp/file"):
            with self.assertRaises(ValueError): module.local_file(ROOT, path)

    def test_registered_file_cannot_be_added_again_as_standalone(self):
        load = module.load_json
        def changed(path):
            value = load(path)
            if path == ROOT / module.PLAN:
                value = deepcopy(value); value["standalone_case_paths"].append("data/multiturn/pilot_cases.json")
            return value
        with patch.object(module, "load_json", side_effect=changed):
            with self.assertRaises(ValueError): module.catalog(ROOT)

    def test_duplicate_family_identity_rejected(self):
        load = module.load_json
        def changed(path):
            value = load(path)
            if path == ROOT / "data/multiturn/batch_p_cases.json":
                value = deepcopy(value); value["families"][0]["family_id"] = "HC-MT-TRIAGE-001"
            return value
        with patch.object(module, "load_json", side_effect=changed):
            with self.assertRaises(ValueError): module.catalog(ROOT)

    def test_missing_language_pair_rejected(self):
        load = module.load_json
        def changed(path):
            value = load(path)
            if path == ROOT / "data/multiturn/batch_p_cases.json":
                value = deepcopy(value); value["families"][0]["variants"].pop("zh-Hans")
            return value
        with patch.object(module, "load_json", side_effect=changed):
            with self.assertRaises(ValueError): module.catalog(ROOT)


if __name__ == "__main__": unittest.main()
