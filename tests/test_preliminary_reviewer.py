import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.preliminary_reviewer import prepare_family, run_family, validate_result
from benchmark.reviews import assess_reviews


FAMILY = "HC-GC-TRIAGE-001"


class PreliminaryReviewerTests(unittest.TestCase):
    def _valid_result(self):
        return {
            "schema_version": "0.1.0", "family_id": FAMILY,
            "disposition": "human_decision_required", "summary": "Source supports urgent care.",
            "findings": [{
                "severity": "medium", "case_ids": ["HC-GC-TRIAGE-001-EN"],
                "area": "source_fit", "observation": "Transport wording needs review.",
                "evidence_ids": ["WHO-HEART-2026"],
                "evidence_limit": "No global transport rule.",
                "proposed_action": "Ask reviewer to specify allowable wording.",
                "human_decision": "Should transport be scored?",
            }],
            "language_review_needed": True, "clinical_review_needed": True,
            "limitations": ["No patient-level data used."],
        }

    def test_prompt_includes_both_languages_and_public_evidence(self):
        prompt, context = prepare_family(FAMILY)
        self.assertIn("HC-GC-TRIAGE-001-EN", prompt)
        self.assertIn("HC-GC-TRIAGE-001-ZH-HANS", prompt)
        self.assertIn("WHO-HEART-2026", context["evidence_ids"])
        self.assertEqual(len(context["case_versions_and_hashes"]), 2)

    def test_public_registry_covers_every_alpha_family(self):
        root = Path(__file__).resolve().parents[1]
        families = {
            json.loads(line)["metadata"]["case_family_id"]
            for line in (root / "data/alpha/global_core_cases.jsonl").read_text(encoding="utf-8").splitlines()
        }
        for family_id in families:
            _, context = prepare_family(family_id)
            self.assertTrue(context["evidence_ids"], family_id)

    def test_validator_rejects_waived_human_gate_and_unknown_evidence(self):
        _, context = prepare_family(FAMILY)
        valid = self._valid_result()
        validate_result(valid, context)
        invalid = json.loads(json.dumps(valid))
        invalid["clinical_review_needed"] = False
        with self.assertRaises(ValueError):
            validate_result(invalid, context)
        invalid = json.loads(json.dumps(valid))
        invalid["findings"][0]["case_ids"] = [{"malformed": "object"}]
        with self.assertRaises(ValueError):
            validate_result(invalid, context)
        invalid = json.loads(json.dumps(valid))
        invalid["findings"][0]["evidence_ids"] = ["invented-source"]
        with self.assertRaises(ValueError):
            validate_result(invalid, context)

    def test_ai_output_does_not_clear_human_gate(self):
        _, context = prepare_family(FAMILY)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch("benchmark.preliminary_reviewer.OUTPUT", output), patch(
                "benchmark.preliminary_reviewer.subprocess.run"
            ) as process:
                def fake_run(command, **kwargs):
                    index = command.index("--output-last-message")
                    Path(command[index + 1]).write_text(json.dumps(self._valid_result()), encoding="utf-8")
                    return type("Completed", (), {"returncode": 0, "stderr": ""})()
                process.side_effect = fake_run
                path = run_family(FAMILY)
                record = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(record["record_type"], "ai_preliminary_review_not_human_approval")
                self.assertIn("read-only", process.call_args.args[0])
                reviews = assess_reviews(
                    Path(__file__).resolve().parents[1] / "data/alpha/global_core_cases.jsonl",
                    Path(__file__).resolve().parents[1] / "data/reviews",
                    {"required_clinical_approvals": 1, "required_language_approvals": 1},
                )
                self.assertIn("HC-GC-TRIAGE-001-EN", reviews["review_queue"]["clinical_review_pending"])


if __name__ == "__main__":
    unittest.main()
