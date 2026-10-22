import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_json
from benchmark.pubmed_derived_case_audit import audit_derived_cases


class PubmedDerivedCaseAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.cases = load_json(root / "data/multiturn/batch_h_cases.json")
        cls.ledger = load_json(root / "data/multiturn/batch_h_provenance.json")

    def test_exact_requirements_have_independent_sources(self):
        result = audit_derived_cases(self.cases, self.ledger)
        self.assertEqual(result["families"], 2)
        self.assertEqual(result["mapped_requirements"], 12)

    def test_case_report_cannot_be_used_as_answer_evidence(self):
        altered = deepcopy(self.ledger)
        altered["records"][0]["requirement_support"][0]["guidance_url"] = altered["records"][0]["published_case_or_series"]
        with self.assertRaisesRegex(ValueError, "independent guidance"):
            audit_derived_cases(self.cases, altered)

    def test_missing_requirement_source_is_rejected(self):
        altered = deepcopy(self.ledger)
        altered["records"][1]["requirement_support"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete exact-requirement"):
            audit_derived_cases(self.cases, altered)

    def test_distinctive_published_detail_in_prompt_is_rejected(self):
        altered = deepcopy(self.cases)
        altered["families"][0]["variants"]["en"]["turns"][0]["user"] += " tramadol"
        with self.assertRaisesRegex(ValueError, "distinctive published-case"):
            audit_derived_cases(altered, self.ledger)

    def test_batch_i_requires_explicit_consent_exception_and_independent_sources(self):
        root = Path(__file__).resolve().parents[1]
        cases = load_json(root / "data/multiturn/batch_i_cases.json")
        ledger = load_json(root / "data/multiturn/batch_i_provenance.json")
        with self.assertRaisesRegex(ValueError, "eligible frozen PubMed"):
            audit_derived_cases(cases, ledger)
        result = audit_derived_cases(cases, ledger, allow_unresolved_consent=True)
        self.assertEqual((result["families"], result["mapped_requirements"]), (1, 6))
        changed = deepcopy(cases)
        changed["families"][0]["variants"]["en"]["turns"][0]["user"] += " psoriasis"
        with self.assertRaisesRegex(ValueError, "distinctive published-case"):
            audit_derived_cases(changed, ledger, allow_unresolved_consent=True)
