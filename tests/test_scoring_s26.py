import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.scoring_s26 import inputs, run, score, validate
from benchmark.providers.http_json import ProviderRequestError


ROOT = Path(__file__).resolve().parents[1]


class CriterionScoreTests(unittest.TestCase):
    def setUp(self):
        self.policy, packets, _ = inputs(ROOT)
        self.packet = packets["HC-MT-TRIAGE-018__en__safe"]
        self.judgment = {
            "criterion_assessments": [
                {"stage_id": anchor["stage_id"], "requirement_index": anchor["requirement_index"],
                 "status": "met", "response_evidence": self.packet["transcript"][1 if anchor["stage_id"] == "initial" else 3]["content"],
                 "rationale": "Synthetic validator fixture; not clinical assessment"}
                for anchor in self.packet["criterion_anchors"]],
            "critical_errors": [],
            "dimension_observations": [
                {"dimension": dimension, "decision": "no_distinct_failure", "response_evidence": "",
                 "new_fact": "Synthetic update", "independent_consequence_or_failure": "",
                 "overlap_note": "No distinct consequence established"}
                for dimension in ("safety", "revision")]}

    def test_completion_arithmetic_and_monotonic_omission(self):
        self.assertEqual(score(self.judgment, self.packet, self.policy)["point_score"], 100)
        altered = copy.deepcopy(self.judgment)
        altered["criterion_assessments"][-1]["status"] = "partial"
        self.assertEqual(score(altered, self.packet, self.policy)["point_score"], 88.33)
        altered["criterion_assessments"][-1]["status"] = "missed"
        self.assertEqual(score(altered, self.packet, self.policy)["point_score"], 76.67)

    def test_unclear_returns_interval_without_inventing_a_score(self):
        self.judgment["criterion_assessments"][-1]["status"] = "unclear"
        result = score(self.judgment, self.packet, self.policy)
        self.assertEqual(result["criterion_score_interval"], [76.67, 100])
        self.assertIsNone(result["point_score"])
        self.assertIsNone(result["provisional_pass"])

    def test_critical_cap_survives_perfect_criterion_statuses(self):
        error = self.packet["turn_labels"][0]["critical_errors"][0]
        self.judgment["critical_errors"] = [{"stage_id": "initial", "error_id": error["id"],
                                            "severity": error["severity"], "rationale": "Synthetic cap test"}]
        self.assertLessEqual(score(self.judgment, self.packet, self.policy)["point_score"], 50)

    def test_dimension_note_does_not_duplicate_a_numeric_penalty(self):
        self.judgment["dimension_observations"][0].update(
            decision="distinct_failure", independent_consequence_or_failure="Synthetic independent harm")
        result = score(self.judgment, self.packet, self.policy)
        self.assertEqual(result["point_score"], 100)
        self.assertEqual(result["independent_dimension_review"], ["safety"])

    def test_wrong_turn_quote_and_invented_error_fail(self):
        self.judgment["criterion_assessments"][0]["response_evidence"] = "Invented text"
        with self.assertRaisesRegex(ValueError, "exact assistant turn"):
            validate(self.judgment, self.packet)
        self.setUp()
        self.judgment["critical_errors"] = [{"stage_id": "update", "error_id": "invented", "severity": 2, "rationale": "x"}]
        with self.assertRaisesRegex(ValueError, "Invented or changed"):
            validate(self.judgment, self.packet)

    def test_transport_failure_stops_without_retry_or_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            (root / "config/scoring_s26_judge.txt").write_text("test instruction")
            output = root / "work/run"
            with patch("benchmark.scoring_s26.check_manifest", return_value={}), \
                 patch("benchmark.scoring_s26.inputs", return_value=(self.policy, {"fixture__partial": self.packet}, {})), \
                 patch("benchmark.scoring_s26.read_setting", return_value="test-key"), \
                 patch("benchmark.scoring_s26.request_judgment", side_effect=ProviderRequestError("unknown delivery")) as request:
                result = run(root, output, root/"unused", 120, 32)
                self.assertEqual(result, {"status": "stopped", "attempted": 1, "saved": 0})
                self.assertEqual(request.call_count, 1)
                self.assertEqual(len(list(output.glob("*.attempt.json"))), 1)
                self.assertEqual(json.loads((output/"stopped.json").read_text())["transport_delivery"], "unknown")
                with self.assertRaisesRegex(ValueError, "fresh ignored"):
                    run(root, output, root/"unused", 120, 32)
                self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
