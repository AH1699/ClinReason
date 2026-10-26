from copy import deepcopy
from pathlib import Path
import unittest

from benchmark.config import load_json
from scripts import audit_batch_p as batch

ROOT = Path(__file__).resolve().parents[1]


class BatchPTests(unittest.TestCase):
    def setUp(self): self.data = {name: load_json(ROOT / path) for name,path in batch.FILES.items()}

    def test_two_new_families_complete_maps_and_references(self):
        value = batch.audit(ROOT)
        self.assertEqual((value["new_standalone_families"], value["variants"], value["mapped_criterion_positions"]), (2,4,12))
        self.assertEqual((value["default_portfolio_additions"], value["live_calls"], value["numeric_scores"]), (0,0,0))
        self.assertEqual(value["triage_transitions"], {"routine→routine": 1})

    def test_changed_case_invalidates_labels_and_sources(self):
        self.data["cases"]["families"][0]["variants"]["en"]["turns"][0]["user"] += " extra"
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_source_mapping_must_cover_every_position(self):
        self.data["provenance"]["records"][0]["requirement_support"].pop()
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_unlisted_source_rejected(self):
        self.data["provenance"]["records"][1]["requirement_support"][0]["guidance_url"] = "https://example.com"
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_stale_provenance_case_binding_rejected(self):
        self.data["provenance"]["records"][0]["case_hashes"]["en"] = "0" * 64
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_missing_language_or_changed_error_cannot_pass(self):
        self.data["controls"]["probes"][1] = deepcopy(self.data["controls"]["probes"][0])
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_partial_is_exact_single_component_omission(self):
        for probe in self.data["controls"]["probes"]:
            value = batch.materialize(probe)
            separator = " " if probe["language"] == "en" else ""
            self.assertEqual(value["partial_update_response"], separator.join(probe["safe_components"][:2]))
            self.assertNotIn(probe["safe_components"][2], value["partial_update_response"])

    def test_privacy_and_review_status_not_promoted(self):
        self.data["provenance"]["records"][0]["review_complete"] = True
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_critical_error_requires_existing_id(self):
        self.data["controls"]["probes"][0]["expected_unsafe_error_id"] = "NOT-IN-CASE"
        with self.assertRaises(ValueError): batch.validate(self.data)


if __name__ == "__main__": unittest.main()
