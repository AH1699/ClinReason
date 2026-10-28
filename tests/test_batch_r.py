from copy import deepcopy
from pathlib import Path
import unittest

from benchmark.config import load_json
from scripts import audit_batch_r as batch

ROOT = Path(__file__).resolve().parents[1]


class BatchRTests(unittest.TestCase):
    def setUp(self):
        self.data = {k: load_json(ROOT / p) for k, p in batch.FILES.items()}

    def test_complete_author_package_and_no_promotion(self):
        result = batch.audit(ROOT)
        self.assertEqual(result["new_standalone_families"], 2)
        self.assertEqual(result["mapped_criterion_positions"], 14)
        self.assertEqual(len(result["packet_hashes"]), 12)
        self.assertEqual(result["live_calls"], 0)
        self.assertEqual(result["numeric_scores"], 0)
        self.assertEqual(result["overlap_check"]["report_identity_overlaps"], 0)

    def test_stale_case_and_anchor_fail(self):
        for key in ("cases", "anchors"):
            data = deepcopy(self.data)
            if key == "cases": data[key]["families"][0]["variants"]["en"]["turns"][0]["user"] += " changed"
            else: data[key]["families"][0]["case_hashes"]["en"] = "stale"
            with self.assertRaises(ValueError): batch.validate(data)

    def test_source_map_coverage_hash_url_and_type_fail_closed(self):
        for kind in ("missing", "duplicate", "hash", "url", "type"):
            data = deepcopy(self.data); rows = data["provenance"]["records"][0]["requirement_support"]
            if kind == "missing": rows.pop()
            elif kind == "duplicate": rows[1] = deepcopy(rows[0])
            elif kind == "hash": rows[0]["case_hashes"]["en"] = "stale"
            elif kind == "url": rows[0]["guidance_url"] = "https://example.org"
            else: rows[0]["support_type"] = "clinically_approved"
            with self.assertRaises(ValueError): batch.validate(data)

    def test_private_material_or_promoted_review_rejected(self):
        for field in ("private_records_used", "source_patient_reconstructed", "images_used", "review_complete"):
            data = deepcopy(self.data); record = data["provenance"]["records"][0]
            if field == "review_complete": record[field] = True
            else: record["privacy_check"][field] = True
            with self.assertRaises(ValueError): batch.validate(data)

    def test_missing_license_or_attribution_rejected(self):
        for field in ("license", "attribution", "correction_retraction_screen"):
            data = deepcopy(self.data); data["provenance"]["records"][0]["report"][field] = ""
            with self.assertRaises(ValueError): batch.validate(data)

    def test_controls_missing_duplicate_stale_and_bad_deletion_rejected(self):
        for kind in ("missing", "duplicate", "stale", "deletion"):
            data = deepcopy(self.data); rows = data["controls"]["probes"]
            if kind == "missing": rows.pop()
            elif kind == "duplicate": rows[1] = deepcopy(rows[0])
            elif kind == "stale": rows[0]["case_content_hash"] = "stale"
            else: rows[0]["partial_omitted_requirement_index"] = 5
            with self.assertRaises(ValueError): batch.validate(data)

    def test_partial_is_exact_component_deletion(self):
        for probe in self.data["controls"]["probes"]:
            value = batch.shared.materialize(probe)
            separator = " " if probe["language"] == "en" else ""
            self.assertEqual(value["partial_update_response"], separator.join(
                x for i, x in enumerate(probe["safe_components"], 1) if i != probe["partial_omitted_requirement_index"]))


if __name__ == "__main__": unittest.main()
