"""No-network tests for the bounded S13 judge run and exact saved audit."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.providers.http_json import ProviderRequestError
from benchmark.scoring_probe_run import audit_saved, load_inputs, prepare_run, run_live


class FixtureJudge:
    def __init__(self, model, *, fail_after=None):
        self.model_id = model
        self.model_version = model
        self.calls = 0
        self.fail_after = fail_after

    def evaluate(self, packet):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ProviderRequestError("simulated unknown delivery")
        update = packet["transcript"][3]["content"]
        if "still cannot tell" in update or "仍不能判断" in update:
            statuses, safety, requirements, revision = ["partial", "met", "met"], 4, 3, 2
        elif "New eye swelling" not in update and "若新出现" not in update:
            statuses, safety, requirements, revision = ["met", "met", "partial"], 3, 3, 3
        elif "Continue proportionate" not in update and "继续相称" not in update:
            statuses, safety, requirements, revision = ["met", "partial", "met"], 4, 3, 4
        else:
            statuses, safety, requirements, revision = ["met", "met", "met"], 4, 4, 4
        assessments = []
        for anchor in packet["criterion_anchors"]:
            stage = anchor["stage_id"]
            text = packet["transcript"][1 if stage == "initial" else 3]["content"]
            assessments.append({
                "stage_id": stage, "requirement_index": anchor["requirement_index"],
                "status": "met" if stage == "initial" else statuses[anchor["requirement_index"] - 1],
                "response_evidence": text[:10], "rationale": "Fixture evidence only.",
            })
        return {
            "stage_scores": [
                {"stage_id": "initial", "safety": 4, "requirements": 4, "rationale": "Fixture."},
                {"stage_id": "update", "safety": safety, "requirements": requirements, "rationale": "Fixture."},
            ],
            "revision_score": revision, "critical_errors": [], "confidence": 0.8,
            "requires_human_review": False, "overall_rationale": "Fixture only.",
            "criterion_assessments": assessments,
        }


class ScoringProbeRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_inputs(Path(__file__).resolve().parents[1])

    def judges(self, *, fail_after=None):
        return {spec["id"]: FixtureJudge(spec["model"], fail_after=fail_after)
                for spec in self.inputs["roster"]["judges"]}

    def test_dry_plan_has_exact_frozen_hashes_without_keys(self):
        with patch("benchmark.scoring_probe_run.read_setting", side_effect=AssertionError("read key")):
            plan, packets = prepare_run(self.inputs)
        self.assertEqual((plan["candidate_calls"], plan["judge_calls_required"]), (0, 16))
        self.assertEqual(len(packets), 8)
        self.assertEqual(len({row["packet_sha256"] for row in plan["packet_hashes"]}), 8)

    def test_mocked_run_then_independent_saved_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fresh"
            judges = self.judges()
            with patch("benchmark.scoring_probe_run.read_setting", side_effect=AssertionError("read key")):
                result = run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                                  max_api_calls=16, judge_instances=judges)
            self.assertEqual(result["judge_calls"], 16)
            self.assertEqual([judge.calls for judge in judges.values()], [8, 8])
            self.assertEqual(len(list(target.glob("*.judgment.json"))), 16)
            audit = audit_saved(self.inputs, target)
            self.assertEqual(audit["completed_judge_calls"], 16)
            self.assertEqual(len(audit["contrasts"]), 12)
            self.assertEqual(len(audit["judge_pairs"]), 8)
            self.assertEqual(len(audit["baseline_checks"]), 4)
            self.assertEqual(len(audit["bilingual_counterparts"]), 8)
            self.assertTrue(all(row["targeted_status_match"] for row in audit["contrasts"]))
            self.assertFalse(any(row["pass_split"] for row in audit["judge_pairs"]))
            with self.assertRaises(FileExistsError):
                run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                         max_api_calls=16, judge_instances=self.judges())

    def test_tampered_score_or_packet_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fresh"
            run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                     max_api_calls=16, judge_instances=self.judges())
            path = next(target.glob("*.judgment.json"))
            original = json.loads(path.read_text(encoding="utf-8"))
            altered = {**original, "score": {**original["score"], "gated_score": 7}}
            path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not recompute"):
                audit_saved(self.inputs, target)
            altered = {**original, "packet_sha256": "changed"}
            path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "conflicts with report"):
                audit_saved(self.inputs, target)

    def test_hard_cap_and_stopped_partial_run(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fresh"
            with self.assertRaisesRegex(ValueError, "exactly"):
                run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                         max_api_calls=17, judge_instances=self.judges())
            self.assertFalse(target.exists())
            judges = self.judges(fail_after=1)
            with self.assertRaisesRegex(ProviderRequestError, "stopped"):
                run_live(self.inputs, output_dir=target, env_file=Path("unused"),
                         max_api_calls=16, judge_instances=judges)
            failure = json.loads((target / "failure.json").read_text(encoding="utf-8"))
            self.assertEqual((failure["attempted_calls"], failure["completed_judgments"]), (2, 1))
            self.assertFalse((target / "report.json").exists())
            self.assertEqual(len(list(target.glob("*.judgment.json"))), 1)


if __name__ == "__main__":
    unittest.main()
