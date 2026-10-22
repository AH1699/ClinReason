"""No-network tests for S17 preregistration and non-enforced saved-result flags."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.scoring_dimension_evidence_s17 import (
    S17_RUN_STATUS, audit_clean_live, describe_pairs, prepare_live_run, preregister_plan,
)
from benchmark.scoring_dimension_fresh_run import load_inputs, run_live


class FakeJudge:
    def __init__(self, model):
        self.model_version = model
        self.calls = 0

    def evaluate(self, packet):
        self.calls += 1
        omitted = ("New urinary symptoms" not in packet["transcript"][-1]["content"]
                   and "新发尿路症状" not in packet["transcript"][-1]["content"])
        assessments = []
        for anchor in packet["criterion_anchors"]:
            stage = anchor["stage_id"]
            content = packet["transcript"][1 if stage == "initial" else 3]["content"]
            assessments.append({
                "stage_id": stage, "requirement_index": anchor["requirement_index"],
                "status": "partial" if omitted and stage == "update"
                and anchor["requirement_index"] == 3 else "met",
                "response_evidence": content[:8], "rationale": "Offline fixture.",
            })
        return {
            "stage_scores": [
                {"stage_id": "initial", "safety": 4, "requirements": 4, "rationale": "Fixture."},
                {"stage_id": "update", "safety": 3 if omitted else 4,
                 "requirements": 3 if omitted else 4, "rationale": "Fixture."},
            ],
            "revision_score": 4, "critical_errors": [], "confidence": 0.8,
            "requires_human_review": omitted, "overall_rationale": "Offline fixture.",
            "criterion_assessments": assessments,
        }


class S17DimensionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_preregistration_is_bound_to_only_punctuation_edit(self):
        plan = preregister_plan(self.root)
        self.assertEqual(plan["judge_calls_max"], 8)
        self.assertEqual(plan["candidate_calls"], 0)
        self.assertEqual(len(plan["packets"]), 4)
        self.assertEqual(len({row["packet_sha256"] for row in plan["packets"]}), 4)

    def test_additional_chinese_change_rejected(self):
        from benchmark.config import load_json
        original = load_json(self.root / "data/multiturn/scoring_dimension_probe_reason015_s17_v2.json")
        altered = copy.deepcopy(original)
        altered["languages"][1]["base_update_segments"][0] += " extra"
        with patch("benchmark.scoring_dimension_evidence_s17.load_json", side_effect=lambda path: (
            altered if str(path).endswith("scoring_dimension_probe_reason015_s17_v2.json")
            else load_json(path)
        )):
            with self.assertRaisesRegex(ValueError, "exceeds trailing punctuation"):
                preregister_plan(self.root)

    def test_mocked_bounded_run_and_saved_audit(self):
        prepared = prepare_live_run(self.root)
        judges = {spec["id"]: FakeJudge(spec["model"]) for spec in prepared[0]["judges"]}
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "s17"
            run_live(load_inputs(self.root), output_dir=target, env_file=Path("unused"),
                     max_api_calls=8, judge_instances=judges, prepared=prepared,
                     run_status=S17_RUN_STATUS)
            result = audit_clean_live(self.root, target)
            self.assertEqual(result["completed_judge_calls"], 8)
            self.assertEqual([judge.calls for judge in judges.values()], [4, 4])

    def test_review_flags_never_change_saved_scores(self):
        s14 = {
            "completed_judge_calls": 16, "candidate_calls": 0,
            "judge_pairs": [
                {"case_id": f"C-{language}", "variant": "safety_net_omission",
                 "judge_scores": {judge: 82.5 for judge in ("gemini-judge", "grok-judge")}}
                for language in ("EN", "ZH-HANS")
            ],
            "contrasts": [
                {"case_id": f"C-{language}", "judge_id": judge,
                 "variant": "safety_net_omission",
                 "observed_update_statuses": ["met", "met", "partial"],
                 "delta_from_baseline": {"requirements": -1, "safety": -1,
                                         "revision": -1, "gated_score": -17.5}}
                for language in ("EN", "ZH-HANS") for judge in ("gemini-judge", "grok-judge")
            ],
        }
        s16 = {"completed_judge_calls": 8, "candidate_calls": 0,
               "pairs": [
                   {"case_id": f"D-{language}", "judge_id": judge,
                    "omission_update_statuses": ["met", "met", "partial"],
                    "delta_from_baseline": {"requirements": -1, "safety": 0,
                                            "revision": 0, "gated_score": -5},
                    "omission_pass": True}
                   for language in ("EN", "ZH-HANS") for judge in ("gemini-judge", "grok-judge")
               ]}
        original = copy.deepcopy((s14, s16))
        report = describe_pairs(s14, s16, 70)
        self.assertEqual(report["saved_omission_pairs"], 8)
        self.assertEqual(report["flag_counts"]["multi_dimension_overlap_review"], 4)
        self.assertEqual(report["flag_counts"]["provisional_pass_with_omission_review"], 8)
        self.assertEqual((s14, s16), original)


if __name__ == "__main__":
    unittest.main()
