import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_jsonl
from benchmark.reviews import assess_reviews, build_review_template, case_content_hash


class ReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.cases_path = cls.root / "data" / "alpha" / "global_core_cases.jsonl"
        cls.cases = load_jsonl(cls.cases_path)
        cls.english_case = next(case for case in cls.cases if case["language"] == "en")

    def _clinical_record(self):
        record = build_review_template(
            self.english_case,
            review_type="clinical",
            reviewer_id="reviewer_clinical_01",
            role="clinician",
            qualification_scope="General clinical safety review",
            jurisdiction_scope="global_core",
        )
        record["decision"] = "approve"
        for field in (
            "prompt_valid",
            "reference_valid",
            "requirements_observable",
            "critical_errors_valid",
            "sources_sufficient",
            "scope_appropriate",
        ):
            record["checks"][field] = True
        record["required_changes"] = []
        record["notes"] = "Approved for the declared Global Core scope."
        return record

    def _assess(self, records):
        with tempfile.TemporaryDirectory() as directory:
            reviews_path = Path(directory) / "reviews.jsonl"
            reviews_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            return assess_reviews(
                self.cases_path,
                reviews_path,
                {"required_clinical_approvals": 1, "required_language_approvals": 1},
            )

    def test_template_is_bound_to_exact_case_content(self):
        record = self._clinical_record()
        self.assertEqual(record["case_id"], self.english_case["id"])
        self.assertEqual(record["case_version"], self.english_case["version"])
        self.assertEqual(record["case_content_hash"], case_content_hash(self.english_case))

    def test_valid_approval_clears_one_clinical_gate(self):
        result = self._assess([self._clinical_record()])
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(result["review_record_count"], 1)
        self.assertNotIn(
            self.english_case["id"],
            result["review_queue"]["clinical_review_pending"],
        )
        self.assertIn(
            self.english_case["id"],
            result["review_queue"]["review_gates_complete"],
        )

    def test_stale_case_hash_cannot_clear_gate(self):
        record = self._clinical_record()
        record["case_content_hash"] = "0" * 64
        result = self._assess([record])
        self.assertFalse(result["valid"])
        self.assertIn("STALE_CASE_REVIEW", {issue["code"] for issue in result["issues"]})
        self.assertIn(
            self.english_case["id"],
            result["review_queue"]["clinical_review_pending"],
        )

    def test_promotion_metadata_does_not_invalidate_content_hash(self):
        promoted = deepcopy(self.english_case)
        promoted["status"] = "clinician_validated"
        promoted["metadata"]["clinician_validated"] = True
        promoted["metadata"]["reviewer_ids"] = ["reviewer_clinical_01"]
        self.assertEqual(
            case_content_hash(promoted),
            case_content_hash(self.english_case),
        )

    def test_prompt_change_invalidates_content_hash(self):
        changed = deepcopy(self.english_case)
        changed["prompt"] += " Material change."
        self.assertNotEqual(
            case_content_hash(changed),
            case_content_hash(self.english_case),
        )

    def test_author_cannot_independently_approve_own_case(self):
        record = self._clinical_record()
        record["reviewer"]["pseudonymous_id"] = self.english_case["metadata"]["author_id"]
        result = self._assess([record])
        self.assertFalse(result["valid"])
        self.assertIn("SELF_REVIEW", {issue["code"] for issue in result["issues"]})

    def test_latest_review_by_same_reviewer_controls_gate(self):
        approval = self._clinical_record()
        revision = deepcopy(approval)
        revision["id"] = approval["id"] + "_revision"
        revision["supersedes_review_id"] = approval["id"]
        revision["created_at"] = "2099-01-01T00:00:00Z"
        revision["decision"] = "revise"
        revision["checks"]["reference_valid"] = False
        revision["required_changes"] = ["Revise the reference behavior."]
        result = self._assess([approval, revision])
        self.assertTrue(result["valid"], result["issues"])
        self.assertIn(
            self.english_case["id"],
            result["review_queue"]["clinical_review_pending"],
        )

    def test_language_review_requires_permitted_role(self):
        translated_case = next(
            case
            for case in self.cases
            if case["metadata"]["translation_method"] != "original"
        )
        record = build_review_template(
            translated_case,
            review_type="language_equivalence",
            reviewer_id="reviewer_02",
            role="language_reviewer",
            qualification_scope="Bilingual language review",
            jurisdiction_scope="global_core",
        )
        record["reviewer"]["role"] = "clinician"
        result = self._assess([record])
        self.assertFalse(result["valid"])
        self.assertIn(
            "REVIEWER_ROLE_MISMATCH",
            {issue["code"] for issue in result["issues"]},
        )


if __name__ == "__main__":
    unittest.main()
