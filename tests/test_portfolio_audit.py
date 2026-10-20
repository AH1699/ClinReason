import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmark.config import load_json
from benchmark.portfolio_audit import _validate_queue, audit_portfolio


class PortfolioAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_current_public_portfolio_and_provenance_boundaries(self):
        report = audit_portfolio(self.root)
        self.assertEqual(report["family_count"], 104)
        self.assertEqual(report["language_variant_count"], 208)
        self.assertEqual(report["tracks"], {
            "alpha_single_turn": 32, "patient_multiturn": 30, "professional": 42,
        })
        self.assertEqual(report["published_case_adaptations"], 26)
        self.assertEqual(report["alpha_families_missing_source_registry"], [])
        self.assertEqual(report["alpha_families_without_matching_registry_url"], [])
        self.assertEqual(report["families_with_criterion_level_verified_source_mapping"], 0)
        self.assertEqual(report["calibration_family_count"], 0)
        self.assertEqual(report["hidden_gold_family_count"], 0)
        self.assertEqual(report["prospective_calibration_draft_family_count"], 10)
        self.assertEqual(report["prospective_calibration_draft_category_counts"], {
            "triage": 4, "medication_safety": 3, "clinical_reasoning": 3,
        })
        self.assertEqual(report["prospective_calibration_anchored_family_count"], 6)
        self.assertEqual(report["prospective_calibration_unanchored_family_count"], 4)
        self.assertEqual(report["prospective_calibration_anchor_variant_count"], 12)
        self.assertEqual(report["prospective_calibration_update_response_example_count"], 36)
        self.assertEqual(report["prospective_hidden_local_draft_family_count_declared"], 1)
        self.assertTrue(report["hidden_local_draft_integrity_verified"])
        self.assertEqual(sum(report["max_critical_error_severity_counts"].values()), 104)
        self.assertGreaterEqual(report["selected_overlap_pair_count"], 8)

    def test_prospective_calibration_is_not_in_default_development_dataset(self):
        config = load_json(self.root / "config/benchmark.json")
        split = load_json(self.root / "data/audit/prospective_split_plan.json")
        for batch in split["prospective_draft_integrity"]["calibration_batches"]:
            self.assertNotIn(batch["path"], config["multiturn_cases_paths"])
        self.assertEqual([batch["family_count"] for batch in split["prospective_draft_integrity"]["calibration_batches"]], [1, 5, 4])
        self.assertEqual(
            [batch["provenance_path"] for batch in split["prospective_draft_integrity"]["calibration_batches"]],
            ["data/calibration/provenance_v1.json", "data/calibration/provenance_batch_b.json", "data/calibration/provenance_batch_c.json"],
        )
        self.assertEqual(split["current_public_portfolio"]["hidden_gold_families"], 0)

    def test_prospective_draft_tamper_or_overlap_is_rejected(self):
        actual_load = load_json
        calibration_suffix = "data/calibration/multiturn_candidates_v1.json"
        hidden_suffix = "work/hidden_candidates/multiturn_candidate_001.json"

        def altered_calibration(path):
            value = actual_load(path)
            if str(path).endswith(calibration_suffix):
                value["families"][0]["family_id"] = "HC-MT-MEDSAFE-007"
            return value

        with patch("benchmark.portfolio_audit.load_json", side_effect=altered_calibration):
            with self.assertRaisesRegex(ValueError, "Calibration draft"):
                audit_portfolio(self.root)

        batch_suffix = "data/calibration/multiturn_candidates_batch_b.json"

        def altered_new_batch(path):
            value = actual_load(path)
            if str(path).endswith(batch_suffix):
                value["families"][0]["variants"]["en"]["turns"][0]["user"] += " altered"
            return value

        with patch("benchmark.portfolio_audit.load_json", side_effect=altered_new_batch):
            with self.assertRaisesRegex(ValueError, "Calibration draft"):
                audit_portfolio(self.root)

        new_batch_suffix = "data/calibration/multiturn_candidates_batch_c.json"

        def altered_third_batch(path):
            value = actual_load(path)
            if str(path).endswith(new_batch_suffix):
                value["families"][0]["variants"]["en"]["turns"][1]["user"] += " altered"
            return value

        with patch("benchmark.portfolio_audit.load_json", side_effect=altered_third_batch):
            with self.assertRaisesRegex(ValueError, "Calibration draft"):
                audit_portfolio(self.root)

        provenance_suffix = "data/calibration/provenance_batch_b.json"

        def altered_provenance(path):
            value = actual_load(path)
            if str(path).endswith(provenance_suffix):
                value["records"][0]["published_case_or_series"] = "https://example.invalid/wrong-case"
            return value

        with patch("benchmark.portfolio_audit.load_json", side_effect=altered_provenance):
            with self.assertRaisesRegex(ValueError, "Calibration draft provenance source mismatch"):
                audit_portfolio(self.root)

        third_provenance_suffix = "data/calibration/provenance_batch_c.json"

        def altered_third_provenance(path):
            value = actual_load(path)
            if str(path).endswith(third_provenance_suffix):
                value["records"][0]["family_id"] = "HC-MT-NOTREAL-001"
            return value

        with patch("benchmark.portfolio_audit.load_json", side_effect=altered_third_provenance):
            with self.assertRaisesRegex(ValueError, "Calibration draft provenance does not cover"):
                audit_portfolio(self.root)

        contrast_suffix = "data/calibration/response_contrasts_v1.json"

        def altered_contrasts(path):
            value = actual_load(path)
            if str(path).endswith(contrast_suffix):
                value["families"][0]["variants"]["en"]["unsafe_update_response"] += " changed"
            return value

        with patch("benchmark.portfolio_audit.load_json", side_effect=altered_contrasts):
            with self.assertRaisesRegex(ValueError, "Calibration draft anchor or contrast hash mismatch"):
                audit_portfolio(self.root)

        calibration = actual_load(self.root / calibration_suffix)

        def altered_hidden(path):
            value = actual_load(path)
            if str(path).endswith(hidden_suffix):
                value["families"][0]["source_refs"][0] = calibration["families"][0]["source_refs"][0]
            return value

        with patch("benchmark.portfolio_audit.load_json", side_effect=altered_hidden):
            with self.assertRaisesRegex(ValueError, "Local hidden candidate"):
                audit_portfolio(self.root)

    def test_overlap_queue_rejects_invalid_or_unknown_pairs(self):
        queue = json.loads((self.root / "data/audit/overlap_and_source_review.json").read_text())
        known = {family_id for entry in queue["overlaps"] for family_id in entry["family_ids"]}
        known.update(entry["family_id"] for entry in queue["source_label_review"])
        _validate_queue(queue, known)
        corrupted = deepcopy(queue)
        corrupted["overlaps"][0]["family_ids"][1] = "HC-PRO-NOTREAL-001"
        with self.assertRaises(ValueError):
            _validate_queue(corrupted, known)
        corrupted = deepcopy(queue)
        corrupted["overlaps"].append(deepcopy(corrupted["overlaps"][0]))
        with self.assertRaises(ValueError):
            _validate_queue(corrupted, known)


if __name__ == "__main__":
    unittest.main()
