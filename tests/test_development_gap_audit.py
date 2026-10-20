import unittest
from pathlib import Path

from benchmark.development_gap_audit import audit_development_gaps


class DevelopmentGapAuditTests(unittest.TestCase):
    def test_configured_portfolio_counts_and_cautions(self):
        report = audit_development_gaps(Path(__file__).resolve().parents[1])
        self.assertEqual(report["public_development_family_count"], 112)
        self.assertEqual(report["public_development_language_variant_count"], 224)
        self.assertEqual(report["approved_calibration_family_count"], 0)
        self.assertEqual(report["hidden_gold_family_count"], 0)
        patient = report["patient_multiturn"]
        self.assertEqual(patient["family_count"], 38)
        self.assertEqual(patient["triage_final_acuity_counts"], {
            "emergency": 11, "self_care": 3, "timely_nonemergency": 2,
        })
        self.assertEqual(patient["single_source_family_count"], 24)
        self.assertEqual(patient["distinct_public_source_url_count"], 48)
        self.assertIn("not_observed_difficulty", report["status"])


if __name__ == "__main__":
    unittest.main()
