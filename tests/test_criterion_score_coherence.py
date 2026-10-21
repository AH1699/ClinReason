"""Portable tests for the read-only criterion/number diagnostic."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_json
from benchmark.criterion_score_coherence import audit_cohort


ROOT = Path(__file__).resolve().parents[1]


def judgment(case_id="HC-MT-TRIAGE-019-EN", judge_id="gemini-judge", *,
             update_safety=2, update_requirements=1, revision=2,
             raw=60, gated=60, passed=False, errors=None):
    errors = errors or []
    return {
        "case_id": case_id, "case_content_hash": "case-hash", "variant": "partial",
        "judge_id": judge_id, "rubric_sha256": "rubric-hash",
        "criterion_anchors_sha256": "anchors-hash", "judge_instruction_sha256": "instruction-hash",
        "judgment": {
            "stage_scores": [
                {"stage_id": "initial", "safety": 4, "requirements": 4},
                {"stage_id": "update", "safety": update_safety, "requirements": update_requirements},
            ],
            "revision_score": revision, "critical_errors": errors,
            "criterion_assessments": [
                {"stage_id": stage, "requirement_index": index, "status": status}
                for stage, values in (("initial", ("met", "met", "met")),
                                      ("update", ("met", "partial", "missed")))
                for index, status in enumerate(values, 1)
            ],
        },
        "score": {"case_id": case_id, "case_content_hash": "case-hash",
                  "raw_score": raw, "gated_score": gated, "pass": passed,
                  "hard_fail": False, "critical_errors": errors},
    }


class CriterionScoreCoherenceTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_json(ROOT / "config/criterion_score_coherence_v1.json")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def save(self, name, row):
        path = Path(self.tmp.name) / name
        path.write_text(json.dumps(row), encoding="utf-8")
        return path

    def test_same_status_pass_split_and_safety_net_overlap(self):
        en = judgment()
        zh = judgment("HC-MT-TRIAGE-019-ZH-HANS", update_safety=3,
                      update_requirements=2, revision=3, raw=77.5, gated=77.5, passed=True)
        paths = [self.save("en.json", en), self.save("zh.json", zh)]
        original = [path.read_bytes() for path in paths]
        report = audit_cohort("test", paths, self.policy)
        self.assertEqual(report["flag_counts"]["same_status_pass_split"], 1)
        self.assertEqual(report["flag_counts"]["same_status_numeric_gap"], 1)
        self.assertEqual(report["flag_counts"]["safety_net_overlap_review"], 2)
        self.assertEqual([path.read_bytes() for path in paths], original)

    def test_severity_one_threshold_dependency(self):
        row = judgment(update_safety=3, update_requirements=2,
                       raw=72.5, gated=67.5,
                       errors=[{"stage_id": "update", "error_id": "over", "severity": 1}])
        result = audit_cohort("test", [self.save("error.json", row)], self.policy)
        self.assertEqual(result["flag_counts"]["severity1_threshold_dependence"], 1)
        self.assertNotIn("severity1_draft_pass", result["flag_counts"])

    def test_rejects_wrong_case_binding_or_mixed_protocol(self):
        row = judgment()
        wrong = deepcopy(row)
        wrong["score"]["case_content_hash"] = "changed"
        with self.assertRaisesRegex(ValueError, "case binding"):
            audit_cohort("test", [self.save("wrong.json", wrong)], self.policy)
        changed = deepcopy(row)
        changed["judge_id"] = "grok-judge"
        changed["rubric_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "Mixed rubric"):
            audit_cohort("test", [self.save("one.json", row), self.save("two.json", changed)], self.policy)

    def test_rejects_unbound_case_and_unrecognized_policy(self):
        path = self.save("one.json", judgment())
        expected = {"case_hashes": {"HC-MT-TRIAGE-019-EN": "different"},
                    "rubric_sha256": "rubric-hash", "judge_instruction_sha256": "instruction-hash",
                    "anchor_hashes": {"anchors-hash"}, "rubric": {}}
        with self.assertRaisesRegex(ValueError, "known case"):
            audit_cohort("test", [path], self.policy, expected)
        bad_policy = {**self.policy, "version": "2"}
        with self.assertRaisesRegex(ValueError, "Unknown coherence policy"):
            audit_cohort("test", [path], bad_policy)

    def test_rejects_tampered_numeric_score_under_bound_rubric(self):
        row = judgment()
        row["score"]["stage_scores"] = {"initial": 100.0, "update": 40.0}
        row["score"]["revision_score"] = 50.0
        expected = {"case_hashes": {row["case_id"]: "case-hash"},
                    "rubric_sha256": "rubric-hash", "judge_instruction_sha256": "instruction-hash",
                    "anchor_hashes": {"anchors-hash"},
                    "rubric": load_json(ROOT / "config/multiturn_rubric.json")}
        path = self.save("valid.json", row)
        self.assertEqual(audit_cohort("test", [path], self.policy, expected)["judgment_count"], 1)
        row["score"]["raw_score"] = 61
        tampered = self.save("tampered.json", row)
        with self.assertRaisesRegex(ValueError, "numeric score"):
            audit_cohort("test", [tampered], self.policy, expected)


if __name__ == "__main__":
    unittest.main()
