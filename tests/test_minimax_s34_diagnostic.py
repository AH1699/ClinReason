from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from benchmark import minimax_s34_diagnostic as diagnostic

ROOT = Path(__file__).resolve().parents[1]


class S34QuoteDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.packet = {"transcript": [{"role": "user", "content": "Software fixture"},
            {"role": "assistant", "content": "甲段。中间内容。乙段。原文……符号。"}]}
        self.judgment = {"criterion_assessments": [{"requirement_index": 2, "response_evidence": "甲段。……乙段。"}]}

    def test_noncontiguous_quote_pieces_do_not_repair_original(self):
        original = deepcopy(self.judgment)
        violations = diagnostic.criterion_quote_violations(self.judgment, self.packet)
        self.assertEqual(len(violations), 1)
        self.assertFalse(violations[0]["whole_quote_matches_initial_answer"])
        self.assertEqual([p["matches_initial_answer"] for p in violations[0]["pieces"]], [True, True])
        self.assertEqual(self.judgment, original)

    def test_literal_span_and_literal_ellipsis_are_not_violations(self):
        for quote in ("甲段。中间内容。", "原文……符号。", ""):
            self.judgment["criterion_assessments"][0]["response_evidence"] = quote
            self.assertEqual(diagnostic.criterion_quote_violations(self.judgment, self.packet), [])

    def test_invented_quote_has_no_literal_piece_and_is_not_repaired(self):
        self.judgment["criterion_assessments"][0]["response_evidence"] = "不存在的改写"
        violation = diagnostic.criterion_quote_violations(self.judgment, self.packet)[0]
        self.assertIsNone(violation["separator"])
        self.assertFalse(violation["pieces"][0]["matches_initial_answer"])

    def test_requires_validation_stop_without_credentials_or_requests(self):
        with patch.object(diagnostic.experiment, "audit", return_value={"stopped": None}), \
                patch.object(diagnostic.experiment, "request") as request, \
                patch.object(diagnostic.experiment, "read_setting") as keys:
            with self.assertRaisesRegex(ValueError, "validation stop"):
                diagnostic.diagnose(ROOT, ROOT / "not-read")
            request.assert_not_called()
            keys.assert_not_called()


if __name__ == "__main__":
    unittest.main()
