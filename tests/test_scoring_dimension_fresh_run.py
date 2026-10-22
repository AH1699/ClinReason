"""Offline mocked S15 judge-only run, cap and saved-output audit."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.providers.http_json import ProviderRequestError
from benchmark.scoring_dimension_fresh_run import audit_saved, load_inputs, prepare_run, run_live


class FixtureJudge:
    def __init__(self, model, *, fail_after=None):
        self.model_version = model
        self.calls = 0
        self.fail_after = fail_after

    def evaluate(self, packet):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ProviderRequestError("simulated uncertain delivery")
        update = packet["transcript"][3]["content"]
        omission = "New urinary symptoms" not in update and "新发尿路症状" not in update
        assessments = []
        for anchor in packet["criterion_anchors"]:
            stage = anchor["stage_id"]
            content = packet["transcript"][1 if stage == "initial" else 3]["content"]
            assessments.append({
                "stage_id": stage, "requirement_index": anchor["requirement_index"],
                "status": "partial" if omission and stage == "update"
                and anchor["requirement_index"] == 3 else "met",
                "response_evidence": content[:8], "rationale": "Fixture only.",
            })
        return {
            "stage_scores": [
                {"stage_id": "initial", "safety": 4, "requirements": 4, "rationale": "Fixture."},
                {"stage_id": "update", "safety": 3 if omission else 4,
                 "requirements": 3 if omission else 4, "rationale": "Fixture."},
            ],
            "revision_score": 4, "critical_errors": [], "confidence": 0.8,
            "requires_human_review": omission, "overall_rationale": "Fixture only.",
            "criterion_assessments": assessments,
        }


class ScoringDimensionFreshRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_inputs(Path(__file__).resolve().parents[1])

    def judges(self, fail_after=None):
        return {spec["id"]: FixtureJudge(spec["model"], fail_after=fail_after)
                for spec in self.inputs["roster"]["judges"]}

    def test_plan_has_four_exact_packets_and_no_credentials(self):
        with patch("benchmark.scoring_dimension_fresh_run.read_setting",
                   side_effect=AssertionError("read key")):
            plan, packets = prepare_run(self.inputs)
        self.assertEqual((plan["candidate_calls"], plan["judge_calls_required"]), (0, 8))
        self.assertEqual(len(packets), 4)
        self.assertEqual(len({item["packet_sha256"] for item in plan["packet_hashes"]}), 4)

    def test_mocked_run_and_independent_saved_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fresh"
            judges = self.judges()
            run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                     max_api_calls=8, judge_instances=judges)
            self.assertEqual([judge.calls for judge in judges.values()], [4, 4])
            result = audit_saved(self.inputs, target)
            self.assertEqual(result["completed_judge_calls"], 8)
            self.assertEqual(len(result["pairs"]), 4)
            self.assertTrue(all(item["author_hypothesis_match"] for item in result["pairs"]))
            with self.assertRaises(FileExistsError):
                run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                         max_api_calls=8, judge_instances=self.judges())

    def test_tampered_saved_score_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fresh"
            run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                     max_api_calls=8, judge_instances=self.judges())
            path = next(target.glob("*.judgment.json"))
            row = json.loads(path.read_text(encoding="utf-8"))
            row["score"]["gated_score"] = 1
            path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not recompute"):
                audit_saved(self.inputs, target)

    def test_hard_cap_and_stopped_partial_run(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fresh"
            with self.assertRaisesRegex(ValueError, "exactly"):
                run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                         max_api_calls=9, judge_instances=self.judges())
            self.assertFalse(target.exists())
            with self.assertRaisesRegex(ProviderRequestError, "stopped"):
                run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                         max_api_calls=8, judge_instances=self.judges(fail_after=1))
            self.assertEqual(len(list(target.glob("*.judgment.json"))), 1)
            self.assertFalse((target / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
