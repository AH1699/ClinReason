"""Offline checks for exact batch-G anchors, contrasts and opt-in language protocol."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmark.answer_language_audit import audit_saved_answer_languages
from benchmark.batch_g_contrasts import select_contrast, validate_contrast_set
from benchmark.cli import main
from benchmark.config import load_json
from benchmark.criterion_anchors import validate_anchor_set
from benchmark.model_matrix import prepare_matrix
from benchmark.multiturn import merge_multiturn_datasets, variant_id
from benchmark.provenance import sha256_text


class BatchGProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        config = load_json(cls.root / "config/benchmark.json")
        cls.dataset = merge_multiturn_datasets([
            load_json(cls.root / path) for path in config["multiturn_cases_paths"]
        ])
        cls.anchors = load_json(cls.root / "config/multiturn_criterion_anchors_batch_g_v1.json")
        cls.contrasts = load_json(cls.root / "data/multiturn/batch_g_contrasts_v1.json")
        cls.roster = load_json(cls.root / "config/model_matrix_batch_g_v1.json")

    def test_exact_eight_variants_and_controlled_contrasts(self):
        self.assertEqual(validate_anchor_set(self.anchors, self.dataset)["variant_count"], 8)
        self.assertEqual(validate_contrast_set(self.contrasts, self.dataset, self.anchors)["probe_count"], 8)
        plan, selected, _, _ = prepare_matrix(self.roster, self.dataset)
        self.assertEqual((len(selected), plan["total_api_calls"]), (8, 96))
        for family, language in selected:
            probe = select_contrast(self.contrasts, variant_id(family, language),
                                    self.dataset, self.anchors)
            self.assertEqual(probe["status"], "synthetic_unreviewed_development_probe")

    def test_stale_contrast_and_wrong_error_rejected(self):
        stale = deepcopy(self.contrasts)
        stale["probes"][0]["case_content_hash"] = "stale"
        with self.assertRaisesRegex(ValueError, "Stale"):
            validate_contrast_set(stale, self.dataset, self.anchors)
        wrong = deepcopy(self.contrasts)
        wrong["probes"][0]["expected_unsafe_error_id"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "not configured"):
            validate_contrast_set(wrong, self.dataset, self.anchors)

    def test_prompt_is_opt_in_and_hashed_in_dry_run(self):
        original = (self.root / "config/candidate_prompt.txt").read_text(encoding="utf-8")
        updated = (self.root / "config/candidate_prompt_bilingual_v2.txt").read_text(encoding="utf-8")
        self.assertNotIn("Answer each turn in the language", original)
        self.assertIn("Answer each turn in the language", updated)
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["model-matrix", "--roster", "config/model_matrix_batch_g_v1.json",
                           "--anchors", "config/multiturn_criterion_anchors_batch_g_v1.json",
                           "--candidate-prompt", "config/candidate_prompt_bilingual_v2.txt"])
        self.assertEqual(status, 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(plan["candidate_instruction_sha256"], sha256_text(updated.strip()))
        self.assertEqual(plan["judge_contract"], "criterion_v2")

    def test_assembly_uses_selected_prompt_for_hash_verification(self):
        with patch("benchmark.cli.assemble_matrix_artifacts", return_value={"status": "fixture"}) as assemble, \
             redirect_stdout(io.StringIO()):
            status = main(["assemble-model-matrix", "--roster", "config/model_matrix_batch_g_v1.json",
                           "--anchors", "config/multiturn_criterion_anchors_batch_g_v1.json",
                           "--candidate-prompt", "config/candidate_prompt_bilingual_v2.txt",
                           "--candidate-id", "grok-46", "--case-id", "HC-MT-TRIAGE-018-EN",
                           "--source-dir", "work/placeholder", "--output-dir", "work/unused-assembly"])
        self.assertEqual(status, 0)
        self.assertIn("Answer each turn in the language", assemble.call_args.kwargs["candidate_instruction"])

    def test_separate_language_audit_flags_wrong_script_without_scoring(self):
        probe = self.contrasts["probes"][1]
        case_id = "HC-MT-TRIAGE-018-ZH-HANS"
        row = {"case_id": case_id, "case_content_hash": probe["case_content_hash"],
               "model_id": "fixture", "turn_outputs": [
                   {"stage_id": "initial", "text": probe["initial_response"]},
                   {"stage_id": "update", "text": self.contrasts["probes"][0]["safe_update_response"]},
               ]}
        instruction = (self.root / "config/candidate_prompt_bilingual_v2.txt").read_text(encoding="utf-8").strip()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "answer.jsonl"
            path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            path.with_suffix(".manifest.json").write_text(json.dumps({
                "candidate_instruction_sha256": sha256_text(instruction),
                "case_revisions": [{"case_id": case_id, "case_content_hash": probe["case_content_hash"]}],
            }), encoding="utf-8")
            report = audit_saved_answer_languages(self.root, [path], expected_instruction=instruction)
            with self.assertRaisesRegex(ValueError, "protocol"):
                audit_saved_answer_languages(self.root, [path], expected_instruction="old protocol")
        self.assertEqual(len(report["flags"]), 1)
        self.assertEqual(report["flags"][0]["stage_id"], "update")
        self.assertEqual(report["verified_candidate_instruction_sha256"], sha256_text(instruction))
        self.assertNotIn("score", report)

    def test_single_probe_dry_run_has_no_provider_call(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["judge-anchored-contrast", "--probe-set", "data/multiturn/batch_g_contrasts_v1.json",
                           "--case-id", "HC-MT-TRIAGE-018-EN",
                           "--anchors", "config/multiturn_criterion_anchors_batch_g_v1.json",
                           "--output-dir", "work/unused-g-contrast"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["judge_calls"], 6)


if __name__ == "__main__":
    unittest.main()
