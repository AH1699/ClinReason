"""Freeze the paired glove-rash near miss before any live judge call."""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.criterion_anchors import validate_anchor_set
from benchmark.multiturn import merge_multiturn_datasets, variant_hash, variant_id


class BatchGNearMissTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        config = load_json(cls.root / "config/benchmark.json")
        cls.dataset = merge_multiturn_datasets([
            load_json(cls.root / path) for path in config["multiturn_cases_paths"]
        ])
        cls.anchors = load_json(cls.root / "config/multiturn_criterion_anchors_batch_g_v1.json")
        cls.base = load_json(cls.root / "data/multiturn/batch_g_contrasts_v1.json")
        cls.probes = [
            load_json(cls.root / "data/multiturn/batch_g_near_miss_019_en_v1.json"),
            load_json(cls.root / "data/multiturn/batch_g_near_miss_019_zh_v1.json"),
        ]

    def test_exact_case_error_and_single_changed_update(self):
        validate_anchor_set(self.anchors, self.dataset)
        family = next(f for f in self.dataset["families"] if f["family_id"] == "HC-MT-TRIAGE-019")
        for probe in self.probes:
            language = probe["language"]
            base = next(p for p in self.base["probes"]
                        if (p["family_id"], p["language"]) == (family["family_id"], language))
            self.assertEqual(probe["status"], "synthetic_unreviewed_development_probe")
            self.assertEqual(probe["case_content_hash"], variant_hash(family, language))
            self.assertEqual(probe["expected_unsafe_error_id"],
                             family["variants"][language]["turns"][1]["critical_errors"][0]["id"])
            self.assertEqual({key: probe[key] for key in (
                "initial_response", "safe_update_response", "partial_update_response"
            )}, {key: base[key] for key in (
                "initial_response", "safe_update_response", "partial_update_response"
            )})
            self.assertNotEqual(probe["unsafe_update_response"], base["unsafe_update_response"])
            self.assertEqual(len({probe[key] for key in (
                "safe_update_response", "partial_update_response", "unsafe_update_response"
            )}), 3)
            self.assertIn("急诊" if language == "zh-Hans" else "emergency-department",
                          probe["unsafe_update_response"])
            output = io.StringIO()
            with redirect_stdout(output):
                status = main([
                    "judge-anchored-contrast", "--probe",
                    f"data/multiturn/batch_g_near_miss_019_{'en' if language == 'en' else 'zh'}_v1.json",
                    "--anchors", "config/multiturn_criterion_anchors_batch_g_v1.json",
                    "--output-dir", "work/unused-near-miss-dry-run",
                ])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["judge_calls"], 6)
            self.assertEqual(variant_id(family, language).endswith("-EN"), language == "en")


if __name__ == "__main__":
    unittest.main()
