import copy
import unittest
from pathlib import Path

from benchmark.scoring_evidence_s24 import validate_contract, validate_record
from benchmark.config import load_json


ROOT = Path(__file__).resolve().parents[1]


class S24EvidenceContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_json(ROOT / "config/scoring_evidence_s24_v1.json")["fixtures"][0]

    def test_versioned_contract_is_non_enforced(self):
        self.assertEqual(validate_contract(ROOT / "config/scoring_evidence_s24_v1.json"), {
            "version": "s24-v1", "fixtures": 3, "proposed_deductions": 0,
            "historical_scores_changed": 0})

    def test_safety_deduction_requires_separate_evidence(self):
        bad = copy.deepcopy(self.fixture)
        bad["safety"]["decision"] = "proposed_deduction"
        with self.assertRaisesRegex(ValueError, "separate evidence"):
            validate_record(bad)

    def test_revision_deduction_requires_separate_evidence(self):
        bad = copy.deepcopy(self.fixture)
        bad["revision"]["decision"] = "proposed_deduction"
        with self.assertRaisesRegex(ValueError, "separate evidence"):
            validate_record(bad)

    def test_deduction_rejects_same_omission(self):
        bad = copy.deepcopy(self.fixture)
        bad["safety"]["decision"] = "proposed_deduction"
        bad["safety"]["independent_consequence"] = "Some consequence"
        bad["safety"]["overlap_status"] = "same"
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_record(bad)

    def test_review_gates_cannot_disappear(self):
        bad = copy.deepcopy(self.fixture)
        bad["review_gates"] = ["methods"]
        with self.assertRaisesRegex(ValueError, "review gates"):
            validate_record(bad)


if __name__ == "__main__":
    unittest.main()
