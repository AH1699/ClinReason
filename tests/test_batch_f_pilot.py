"""Frozen public-development batch-F pilot; no network or clinical approval."""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.criterion_anchors import validate_anchor_set
from benchmark.model_matrix import prepare_matrix
from benchmark.multiturn import merge_multiturn_datasets


class BatchFPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        config = load_json(root / "config/benchmark.json")
        cls.dataset = merge_multiturn_datasets([
            load_json(root / path) for path in config["multiturn_cases_paths"]
        ])
        cls.roster = load_json(root / "config/model_matrix_batch_f_v1.json")
        cls.anchors = load_json(root / "config/multiturn_criterion_anchors_batch_f_v1.json")

    def test_exact_four_family_eight_variant_development_panel(self):
        validated = validate_anchor_set(self.anchors, self.dataset)
        self.assertEqual((validated["family_count"], validated["variant_count"]), (4, 8))
        self.assertEqual(len(self.roster["case_ids"]), 8)
        self.assertEqual({entry["family_id"] for entry in self.anchors["families"]},
                         {case_id.rsplit("-", 1)[0].removesuffix("-ZH")
                          for case_id in self.roster["case_ids"]})
        plan, selected, candidates, judges = prepare_matrix(self.roster, self.dataset)
        self.assertEqual(len(selected), 8)
        self.assertEqual({item["provider"] for item in candidates}, {"gemini", "grok", "minimax"})
        self.assertEqual({item["provider"] for item in judges}, {"gemini", "grok"})
        self.assertEqual((plan["candidate_calls"], plan["judge_calls"], plan["total_api_calls"]),
                         (48, 48, 96))
        for candidate in candidates:
            one, _, _, _ = prepare_matrix(self.roster, self.dataset, candidate_id=candidate["id"])
            self.assertEqual(one["total_api_calls"], 32)

    def test_cli_preview_is_no_network_and_bound_to_new_anchors(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main([
                "model-matrix", "--roster", "config/model_matrix_batch_f_v1.json",
                "--anchors", "config/multiturn_criterion_anchors_batch_f_v1.json",
            ])
        self.assertEqual(status, 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(plan["total_api_calls"], 96)
        self.assertEqual(plan["judge_contract"], "criterion_v2")
        self.assertEqual(plan["status"], "dry_run_no_api_calls_development_only")

    def test_assembly_cli_accepts_frozen_nondefault_roster(self):
        output = io.StringIO()
        with patch("benchmark.cli.assemble_matrix_artifacts", return_value={"status": "fixture"}) as assemble, \
             redirect_stdout(output):
            status = main([
                "assemble-model-matrix", "--roster", "config/model_matrix_batch_f_v1.json",
                "--anchors", "config/multiturn_criterion_anchors_batch_f_v1.json",
                "--candidate-id", "gemini-35-flash-lite",
                "--case-id", "HC-MT-TRIAGE-017-EN",
                "--source-dir", "work/placeholder", "--output-dir", "work/placeholder-output",
            ])
        self.assertEqual(status, 0)
        self.assertEqual(assemble.call_args.args[1]["case_ids"], self.roster["case_ids"])


if __name__ == "__main__":
    unittest.main()
