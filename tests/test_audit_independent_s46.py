"""Sanitized summaries are recomputed and contain no response evidence."""

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_independent_s46 import summarize
from tests.test_independent_eval_s46 import ROOT, default_tier, fixture_prefix, finish, run


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name)
        cls.session = run.Session(ROOT, path / "run", fixture_prefix(path / "source"), "FIXTURE", "offline_fixture")
        finish(cls.session, default_tier)
        cls.summary = summarize(cls.session)

    def test_counts_and_numeric_evidence(self):
        self.assertEqual(self.summary["attempts"], 68)
        self.assertEqual(self.summary["answer_stage_counts"], {m: 4 for m in self.session.spec["candidate_models"]})
        details = self.summary["numeric_judgment_details"]
        self.assertEqual(Counter(d["block"] for d in details), {"control": 24, "development": 8})
        self.assertTrue(all(d["score"]["point_score"] is not None for d in details))

    def test_no_raw_answer_or_quote_fields(self):
        encoded = json.dumps(self.summary)
        for field in ('"response_evidence"', '"rationale"', '"raw"', '"text"', '"payload"', '"jobs"'):
            self.assertNotIn(field, encoded)
        self.assertFalse(self.summary["raw_data_published"])
        self.assertFalse(self.summary["model_rankings_approved"])


if __name__ == "__main__":
    unittest.main()
