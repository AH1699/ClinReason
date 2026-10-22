"""No-network tests for citation-only case-report source intake."""

import copy
import unittest
from pathlib import Path

from benchmark.config import load_json
from benchmark.pubmed_case_intake import audit_intake, audit_source_to_answer


class PubmedCaseIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = load_json(Path(__file__).resolve().parents[1]
                               / "data/evidence/pubmed_case_intake_s16_v1.json")
        cls.answer_map = load_json(Path(__file__).resolve().parents[1]
                                   / "data/evidence/pubmed_source_to_answer_s17_v1.json")

    def test_packet_is_citation_only_and_has_no_case_promotions(self):
        report = audit_intake(self.packet)
        self.assertEqual(report["derived_case_count"], 0)
        self.assertEqual(report["record_count"], 4)
        self.assertEqual(sum(report["status_counts"].values()), 4)

    def test_noncommercial_or_no_derivatives_cannot_be_candidate(self):
        altered = copy.deepcopy(self.packet)
        altered["records"][0]["license"] = "CC BY-NC-ND 4.0"
        with self.assertRaisesRegex(ValueError, "unsuitable license"):
            audit_intake(altered)

    def test_duplicate_or_derived_case_rejected(self):
        altered = copy.deepcopy(self.packet)
        altered["records"][1]["pmid"] = altered["records"][0]["pmid"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit_intake(altered)
        altered = copy.deepcopy(self.packet)
        altered["records"][0]["derived_case_ids"] = ["HC-MT-NEW"]
        with self.assertRaisesRegex(ValueError, "no-case boundary"):
            audit_intake(altered)

    def test_independent_source_to_answer_map_has_no_labels(self):
        result = audit_source_to_answer(self.packet, self.answer_map)
        self.assertEqual(result["candidate_sources"], 3)
        self.assertEqual(result["proposed_behaviors"], 6)
        self.assertEqual(result["derived_case_count"], 0)

    def test_case_report_cannot_be_its_own_answer_evidence(self):
        altered = copy.deepcopy(self.answer_map)
        altered["records"][0]["candidate_behaviors"][0]["independent_source_url"] = (
            self.packet["records"][0]["article_url"]
        )
        with self.assertRaisesRegex(ValueError, "distinct guidance"):
            audit_source_to_answer(self.packet, altered)

    def test_source_map_rejects_derived_case(self):
        altered = copy.deepcopy(self.answer_map)
        altered["records"][0]["derived_case_ids"] = ["HC-MT-NEW"]
        with self.assertRaisesRegex(ValueError, "derived case"):
            audit_source_to_answer(self.packet, altered)


if __name__ == "__main__":
    unittest.main()
