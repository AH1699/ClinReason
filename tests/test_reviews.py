import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_jsonl
from benchmark.cli import main
from benchmark.reviews import (
    assess_reviews,
    build_review_template,
    case_content_hash,
    release_review_issues,
)


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
        record["reviewer"]["conflict_disclosed"] = False
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

    def test_disclosed_conflict_cannot_clear_gate(self):
        record = self._clinical_record()
        record["reviewer"]["conflict_disclosed"] = True
        result = self._assess([record])
        self.assertFalse(result["valid"])
        self.assertIn("CONFLICTED_APPROVAL", {issue["code"] for issue in result["issues"]})
        self.assertIn(
            self.english_case["id"],
            result["review_queue"]["clinical_review_pending"],
        )

    def test_another_reviewers_requested_changes_keep_gate_open(self):
        approval = self._clinical_record()
        revision = deepcopy(approval)
        revision["id"] += "_second_reviewer"
        revision["reviewer"]["pseudonymous_id"] = "reviewer_clinical_02"
        revision["decision"] = "revise"
        revision["checks"]["reference_valid"] = False
        revision["required_changes"] = ["Clarify expected behavior."]
        result = self._assess([approval, revision])
        self.assertTrue(result["valid"], result["issues"])
        status = next(item for item in result["case_status"] if item["case_id"] == self.english_case["id"])
        self.assertEqual(status["clinical_approvals"], 1)
        self.assertFalse(status["clinical_complete"])
        self.assertEqual(status["unresolved_clinical_reviewer_ids"], ["reviewer_clinical_02"])

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

    def test_release_requires_real_review_evidence(self):
        empty = self._assess([])
        issues = release_review_issues([self.english_case], empty)
        self.assertIn("REVIEW_GATE_INCOMPLETE", {issue["code"] for issue in issues})

        approved = self._assess([self._clinical_record()])
        issues = release_review_issues([self.english_case], approved)
        self.assertIn("CLINICAL_REVIEWER_METADATA_MISMATCH", {issue["code"] for issue in issues})

        promoted = deepcopy(self.english_case)
        promoted["metadata"]["reviewer_ids"] = ["reviewer_clinical_01"]
        self.assertEqual(release_review_issues([promoted], approved), [])

    def test_release_cli_requires_matching_reviews_for_bilingual_pair(self):
        family_id = self.english_case["metadata"]["case_family_id"]
        pair = [
            deepcopy(case)
            for case in self.cases
            if case["metadata"]["case_family_id"] == family_id
        ]
        records = []
        for case in pair:
            case["status"] = "clinician_validated"
            case["metadata"]["clinician_validated"] = True
            case["metadata"]["reviewer_ids"] = ["reviewer_clinical_01"]
            if case["language"] != "en":
                case["metadata"]["translation_method"] = "machine_translation_human_reviewed"
                case["metadata"]["translation_reviewer_id"] = "reviewer_language_01"
            clinical = build_review_template(
                case,
                review_type="clinical",
                reviewer_id="reviewer_clinical_01",
                role="clinician",
                qualification_scope="Clinical safety review",
                jurisdiction_scope="global_core",
            )
            clinical["decision"] = "approve"
            clinical["reviewer"]["conflict_disclosed"] = False
            for field in clinical["checks"]:
                if field != "language_equivalent":
                    clinical["checks"][field] = True
            records.append(clinical)
            if case["language"] != "en":
                language = build_review_template(
                    case,
                    review_type="language_equivalence",
                    reviewer_id="reviewer_language_01",
                    role="language_reviewer",
                    qualification_scope="Bilingual review",
                    jurisdiction_scope="global_core",
                )
                language["decision"] = "approve"
                language["reviewer"]["conflict_disclosed"] = False
                language["checks"]["language_equivalent"] = True
                language["checks"]["scope_appropriate"] = True
                records.append(language)

        with tempfile.TemporaryDirectory() as directory:
            cases_path = Path(directory) / "paired.jsonl"
            reviews_path = Path(directory) / "reviews.jsonl"
            cases_path.write_text(
                "\n".join(json.dumps(case, ensure_ascii=False) for case in pair) + "\n",
                encoding="utf-8",
            )
            config_path = self.root / "config" / "benchmark.json"
            arguments = [
                "--config", str(config_path), "validate-data", "--cases", str(cases_path),
                "--reviews", str(reviews_path), "--release-ready",
            ]
            reviews_path.write_text("", encoding="utf-8")
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(arguments), 1)
            self.assertIn("REVIEW_GATE_INCOMPLETE", output.getvalue())

            reviews_path.write_text(
                "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(arguments), 0, output.getvalue())


if __name__ == "__main__":
    unittest.main()
