"""Mechanical fixtures, not clinical labels or model performance."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts import judge_panel_s57 as run
from tests.test_judge_saved_bank_s56 import fixture_bank
from tests.test_mixed_panel_s51 import reply

ROOT = Path(__file__).resolve().parents[1]


def bad_quote(raw):
    field = raw["steps"][0]["content"][0]
    value = json.loads(field["text"])
    value["criterion_assessments"][0]["response_evidence"] = "FABRICATED EVIDENCE NOT IN THE ANSWER"
    field["text"] = json.dumps(value)


def advance(core, until=None, transform=None):
    while until is None or core.index < until:
        if core.prepare() is None:
            break
        core.record(reply(core, transform))
    return core


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = fixture_bank()
        cls.controls = advance(run.Core(ROOT, cls.bank, "5.00"), 36)
        cls.complete = advance(deepcopy(cls.controls))

    def new(self):
        return deepcopy(self.controls)

    def test_complete_324_request_path_uses_no_candidate_generation(self):
        value = run.report(self.complete, "offline_fixture", len(self.complete.accounts))
        self.assertEqual(value["transport_attempts"], 324)
        self.assertEqual(value["new_candidate_calls"], 0)
        self.assertEqual(value["live_calls"], 0)
        self.assertEqual((value["first_complete_pairs"], value["repeat_complete_pairs"]), (72, 72))
        self.assertTrue(value["all_pairs_complete"])
        self.assertTrue(value["all_schedule_rows_disposed"])
        self.assertTrue(value["control_gate"]["pass"])

    def test_one_bad_quote_remains_rejected_but_independent_rows_continue(self):
        core = self.new()
        core.prepare(); failed = deepcopy(core.pending)
        core.record(reply(core, bad_quote))
        self.assertEqual(core.outcomes[37], {"status": "rejected", "category": "judgment_format"})
        self.assertIsNone(core.terminal)
        advance(core)
        self.assertNotIn(run.workflow.judgment_key(failed), core.judgments)
        repeated = next(r for r in core.rows if run.workflow.judgment_key(r) == run.workflow.judgment_key({**failed, "repeat": True}))
        self.assertEqual(core.outcomes[repeated["sequence"]], {"status": "skipped", "reason": "first_judgment_missing"})
        value = run.report(core, "offline_fixture", len(core.accounts))
        self.assertEqual(value["transport_attempts"], 323)
        self.assertEqual((value["first_complete_pairs"], value["repeat_complete_pairs"]), (71, 71))
        self.assertIsNone(value["case_diagnostics"][0]["first"])
        self.assertIsNone(value["case_diagnostics"][0]["repeat"])
        self.assertFalse(value["all_pairs_complete"])
        self.assertEqual(value["development_format_failures"], 1)

    def test_third_cumulative_format_failure_stops_without_retry(self):
        core = self.new()
        for index in range(5):
            core.prepare(); core.record(reply(core, bad_quote if index % 2 == 0 else None))
        self.assertEqual(core.format_failures, 3)
        self.assertEqual(core.terminal, "development_format_failure_limit")
        self.assertIsNone(core.prepare())
        self.assertEqual(len(core.accounts), 41)

    def test_failure_counter_is_shared_by_first_and_repeat(self):
        core = self.new()
        advance(core, 38, bad_quote)
        advance(core, 180)
        # The two missing first stages have no retries; their repeat rows are skipped.
        core.prepare(); self.assertTrue(core.pending["repeat"])
        core.record(reply(core, bad_quote))
        self.assertEqual(core.format_failures, 3)
        self.assertEqual(core.terminal, "development_format_failure_limit")

    def test_invalid_control_stops_immediately(self):
        core = run.Core(ROOT, self.bank, "5.00")
        advance(core, 1, bad_quote)
        self.assertEqual(core.terminal, "invalid_control")
        self.assertEqual(core.format_failures, 0)
        self.assertIsNone(core.prepare())

    def test_valid_controls_with_failed_order_gate_cannot_enter_development(self):
        def erase_order(raw):
            field = raw["steps"][0]["content"][0]
            value = json.loads(field["text"])
            for item in value["criterion_assessments"]: item["status"] = "met"
            value["critical_errors"] = []
            field["text"] = json.dumps(value)
        core = advance(run.Core(ROOT, self.bank, "5.00"), transform=erase_order)
        self.assertEqual(len(core.accounts), 36)
        self.assertEqual(core.terminal, "control_gate_failed")
        value = run.report(core, "offline_fixture", 36)
        self.assertTrue(all(c["first"] is None for c in value["case_diagnostics"]))

    def test_unknown_usage_identity_and_completion_never_continue(self):
        for change in (lambda r: r.pop("usage"), lambda r: r.update(model="wrong"), lambda r: r.update(status="incomplete")):
            core = self.new(); core.prepare(); core.record(reply(core, change))
            self.assertIsNotNone(core.terminal)
            self.assertEqual(core.format_failures, 0)
            self.assertIsNone(core.prepare())

    def test_known_rejected_request_counts_toward_threshold(self):
        core = self.new(); core.threshold = core.monitored + 1
        core.prepare(); core.record(reply(core, bad_quote))
        self.assertEqual(core.terminal, "spend_threshold_reached")
        self.assertEqual(core.format_failures, 1)
        self.assertGreaterEqual(core.monitored, core.threshold)

    def test_pending_request_and_duplicate_reply_are_rejected(self):
        core = self.new(); core.prepare()
        with self.assertRaises(ValueError): core.prepare()
        raw = reply(core); core.record(raw)
        with self.assertRaises(ValueError): core.record(raw)

    def test_holds_and_private_text_exclusion(self):
        value = run.report(self.complete, "offline_fixture", 324)
        self.assertEqual(sum(c["comparative_review_hold"] for c in value["case_diagnostics"]), 8)
        for marker in ('"response_evidence"', '"rationale"', "Fixture gemini", "mean_score"):
            self.assertFalse(marker in json.dumps(value), "Unexpected public marker: " + marker)
        self.assertFalse(value["reporting"]["model_rankings"])
        self.assertFalse(value["reporting"]["pooled_model_means"])
        self.assertFalse(value["historical_judgments_reused"])
        self.assertFalse(value["clinical_validation"])

    def test_all_repeat_payloads_identical_and_stage_visibility_unchanged(self):
        core = self.complete
        for row in core.rows:
            context = core.contexts[row["sequence"]]
            if row["repeat"]:
                key = run.workflow.judgment_key({**row, "repeat": False})
                self.assertEqual(run.guard._json_bytes(context["payload"]), core.first_payloads[key])
            self.assertEqual(len(context["packet"]["transcript"]), 2 if row["stage"] == "initial" else 4)


if __name__ == "__main__":
    unittest.main()
