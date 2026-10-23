import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.batch_n_packet_audit import audit, validate_packet
from benchmark.config import load_json

ROOT = Path(__file__).resolve().parents[1]


class BatchNAnswerPacketTests(unittest.TestCase):
    def setUp(self):
        self.data = load_json(ROOT / "data/multiturn/batch_n_cases.json")
        self.anchors = load_json(ROOT / "config/multiturn_criterion_anchors_batch_n_v1.json")
        self.contrasts = load_json(ROOT / "data/multiturn/batch_n_contrasts_v1.json")
        self.provenance = load_json(ROOT / "data/multiturn/batch_n_provenance.json")

    def check(self):
        return validate_packet(self.data, self.anchors, self.contrasts, self.provenance)

    def test_seven_boundaries_and_six_blinded_controls(self):
        result = audit(ROOT)
        self.assertEqual(result["criterion_positions"], 7)
        self.assertEqual(result["bilingual_criterion_positions"], 14)
        self.assertEqual(result["shared_initial_answers"], 2)
        self.assertEqual(result["update_answer_examples"], 6)
        self.assertEqual(len(set(result["packet_hashes"].values())), 6)
        self.assertEqual(result["judge_calls"], 0)

    def test_case_binding_and_undeclared_answer_edit(self):
        self.data["families"][0]["variants"]["en"]["turns"][1]["user"] += " altered"
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.check()
        self.setUp()
        self.contrasts["probes"][0]["partial_update_response"] += " Added assessment."
        with self.assertRaisesRegex(ValueError, "declared edits"):
            self.check()

    def test_missing_sources_and_missing_anchor(self):
        self.provenance["records"][0]["requirement_support"].pop()
        with self.assertRaisesRegex(ValueError, "source mapping"):
            self.check()
        self.setUp()
        self.anchors["families"][0]["stages"]["update"].pop()
        with self.assertRaisesRegex(ValueError, "Criterion count"):
            self.check()

    def test_missing_or_duplicate_language(self):
        self.contrasts["probes"].pop()
        with self.assertRaisesRegex(ValueError, "paired language"):
            self.check()
        self.setUp()
        self.contrasts["probes"].append(deepcopy(self.contrasts["probes"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check()

    def test_unpaired_deletion_and_partial_unsafe_edit_rejected(self):
        self.contrasts["probes"][1]["construction"]["partial_omitted_requirement_index"] = 2
        with self.assertRaisesRegex(ValueError, "paired answer edits"):
            self.check()
        self.setUp()
        self.contrasts["probes"][0]["construction"]["unsafe_replacements"].pop("4")
        with self.assertRaisesRegex(ValueError, "paired answer edits"):
            self.check()

    def test_no_invented_severe_error(self):
        self.contrasts["probes"][0]["expected_unsafe_error_id"] = "omitted-dialysis-detail"
        with self.assertRaisesRegex(ValueError, "Invented critical error"):
            self.check()


if __name__ == "__main__":
    unittest.main()
