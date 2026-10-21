"""S13 one-edit probe packet stays frozen before any judge call."""

import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_json
from benchmark.multiturn import merge_multiturn_datasets
from benchmark.scoring_probe_prereg import VARIANTS, render_update, validate_prereg


class ScoringProbePreregTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        config = load_json(root / "config/benchmark.json")
        cls.dataset = merge_multiturn_datasets([
            load_json(root / path) for path in config["multiturn_cases_paths"]
        ])
        cls.anchors = load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json")
        cls.rubric = load_json(root / "config/multiturn_rubric.json")
        cls.roster = load_json(root / "config/model_matrix.json")
        cls.instruction = (root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip()
        cls.contrasts = load_json(root / "data/multiturn/batch_g_contrasts_v1.json")
        cls.prereg = load_json(root / "data/multiturn/scoring_coherence_probes_s13_v1.json")

    def validate(self, prereg):
        return validate_prereg(prereg, self.dataset, self.anchors, self.rubric,
                               self.roster, self.instruction, self.contrasts)

    def test_exact_bilingual_eight_packet_no_call_plan(self):
        result = self.validate(self.prereg)
        self.assertEqual(result["status"], "frozen_synthetic_prereg_no_model_calls_or_scores")
        self.assertEqual(result["case_count"], 2)
        self.assertEqual(result["answer_variant_count"], 8)
        self.assertEqual((result["planned_candidate_calls"], result["planned_judge_calls"]), (0, 16))
        self.assertEqual(len({row["packet_sha256"] for row in result["packet_hashes"]}), 8)
        self.assertNotIn("score", result)

    def test_each_update_differs_by_exactly_one_authored_segment(self):
        for item in self.prereg["languages"]:
            base = item["base_update_segments"]
            self.assertEqual(render_update(item, "baseline"), item["separator"].join(base))
            self.assertEqual(render_update(item, "plan_omission"),
                             item["separator"].join([base[0], base[1], base[3]]))
            self.assertEqual(render_update(item, "safety_net_omission"),
                             item["separator"].join(base[:3]))
            self.assertEqual(render_update(item, "revision_failure"),
                             item["separator"].join([item["revision_replacement"], *base[1:]]))
            self.assertEqual(len({render_update(item, variant) for variant in VARIANTS}), 4)

    def test_rejects_changed_case_protocol_or_initial_turn(self):
        for change in ("case_content_hash", "rubric_sha256", "initial_response", "base_contrasts_sha256"):
            altered = deepcopy(self.prereg)
            if change in {"case_content_hash", "initial_response"}:
                altered["languages"][0][change] = "changed"
            else:
                altered[change] = "changed"
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(altered)

    def test_rejects_missing_language_or_answer_edit(self):
        altered = deepcopy(self.prereg)
        altered["languages"] = altered["languages"][:1]
        with self.assertRaises(ValueError):
            self.validate(altered)
        altered = deepcopy(self.prereg)
        altered["languages"][1]["base_update_segments"][3] = ""
        with self.assertRaises(ValueError):
            self.validate(altered)


if __name__ == "__main__":
    unittest.main()
