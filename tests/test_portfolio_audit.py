import json
import unittest
from copy import deepcopy
from pathlib import Path

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
        self.assertEqual(sum(report["max_critical_error_severity_counts"].values()), 104)
        self.assertGreaterEqual(report["selected_overlap_pair_count"], 8)

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
