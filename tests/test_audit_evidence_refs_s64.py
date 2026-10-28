from copy import deepcopy
from pathlib import Path
import unittest

from scripts import audit_evidence_refs_s64 as audit
from tests.test_evidence_refs_s64 import fixture
from tests.test_scoring_s36 import judgment

ROOT = Path(__file__).resolve().parents[1]


class RefAuditTests(unittest.TestCase):
    def test_exercise_has_no_judgment_score_or_source_text(self):
        for full, levels in audit.refs.score.controls(ROOT).values():
            for stage in audit.refs.score.STAGES:
                packet = audit.refs.score.stage_packet(full, stage, levels)
                before = deepcopy(packet)
                result = audit.exercise(packet)
                self.assertEqual(set(result), {"packet_sha256", "stage", "language", "catalog_spans",
                    "exact_text_resolution", "unknown_reference_rejected", "semantic_evidence_relevance_tested"})
                self.assertFalse(result["semantic_evidence_relevance_tested"])
                self.assertTrue(result["exact_text_resolution"])
                self.assertEqual(packet, before)

    def test_different_statuses_and_errors_preserve_arithmetic_and_intervals(self):
        score = audit.refs.score
        policy = {"version": score.VERSION, **score.ARITHMETIC}
        for full, levels in score.controls(ROOT).values():
            packets = [score.stage_packet(full, s, levels) for s in score.STAGES]
            for status in ("met", "partial", "missed", "unclear"):
                old = [judgment(p, status) for p in packets]
                new = [audit.refs.resolve(fixture(p, status), p) for p in packets]
                self.assertEqual(score.combine(*old, full, policy), score.combine(*new, full, policy))
            for error in packets[1]["turn_labels"][0]["critical_errors"]:
                values = [fixture(p) for p in packets]
                values[1]["critical_errors"] = [{"stage_id": "update", "error_id": error["id"],
                    "severity": error["severity"], "rationale": "Mechanical fixture."}]
                new = [audit.refs.resolve(v, p) for v, p in zip(values, packets)]
                old = [judgment(p) for p in packets]; old[1]["critical_errors"] = values[1]["critical_errors"]
                self.assertEqual(score.combine(*old, full, policy), score.combine(*new, full, policy))


if __name__ == "__main__": unittest.main()
