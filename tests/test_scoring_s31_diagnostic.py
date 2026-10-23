from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from benchmark import scoring_s31_diagnostic as diagnostic

ROOT = Path(__file__).resolve().parents[1]


class S31QuoteDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.policy, packets, _ = diagnostic.experiment.inputs(ROOT)
        self.packet = packets["HC-MT-TRIAGE-020__zh-Hans__safe"]
        self.initial = self.packet["transcript"][1]["content"]
        self.update = self.packet["transcript"][3]["content"]
        self.judgment = {
            "criterion_assessments": [{"stage_id": a["stage_id"], "requirement_index": a["requirement_index"],
                "status": "met", "response_evidence": self.initial if a["stage_id"] == "initial" else self.update,
                "rationale": "Software fixture, not a clinical judgment."} for a in self.packet["criterion_anchors"]],
            "critical_errors": [],
            "dimension_observations": [{"dimension": d, "decision": "no_distinct_failure",
                "response_evidence": self.update, "new_fact": "Synthetic update", "independent_consequence_or_failure": "",
                "overlap_note": "Synthetic no-separate-failure fixture."} for d in ("safety", "revision")],
        }

    def test_cross_turn_join_remains_invalid_even_when_pieces_are_literal(self):
        self.judgment["dimension_observations"][0]["response_evidence"] = self.initial + " / " + self.update
        snapshot = deepcopy(self.judgment)
        with self.assertRaisesRegex(ValueError, "observation quote"):
            diagnostic.experiment.base.validate(self.judgment, self.packet)
        violations = diagnostic.observation_quote_violations(self.judgment, self.packet)
        self.assertEqual(len(violations), 1)
        self.assertEqual([p["matching_assistant_stages"] for p in violations[0]["pieces"]], [["initial"], ["update"]])
        self.assertEqual(self.judgment, snapshot)

    def test_one_literal_span_is_accepted_without_new_scoring_rule(self):
        diagnostic.experiment.base.validate(self.judgment, self.packet)
        self.assertEqual(diagnostic.observation_quote_violations(self.judgment, self.packet), [])

    def test_invented_paraphrase_is_not_repaired_or_mapped(self):
        self.judgment["dimension_observations"][1]["response_evidence"] = "Synthetic paraphrase absent from both turns."
        violations = diagnostic.observation_quote_violations(self.judgment, self.packet)
        self.assertEqual(violations[0]["pieces"][0]["matching_assistant_stages"], [])
        self.assertIsNone(violations[0]["separator"])

    def test_diagnosis_requires_saved_validation_stop_and_never_calls_provider(self):
        with patch.object(diagnostic.experiment, "audit", return_value={"stopped": None}), \
                patch.object(diagnostic.experiment, "request") as request:
            with self.assertRaisesRegex(ValueError, "validation stop"):
                diagnostic.diagnose(ROOT, ROOT / "not-read")
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
