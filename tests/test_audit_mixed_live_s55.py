"""Offline report tests only; no live credentials or connections."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_mixed_live_s55 as audit
from tests.test_mixed_panel_s51 import ROOT, imports, reply, advance

live, panel = audit.live, audit.panel


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = imports()
        cls.core = advance(panel.Rehearsal(ROOT, cls.records, mode="offline_fixture"))

    def test_all_72_cells_and_both_judgments_retained(self):
        value = audit.diagnostics(self.core)
        self.assertEqual(len(value["conversations"]), 72)
        self.assertEqual(len(value["controls"]), 24)
        self.assertTrue(all(c["first"] and c["repeat"] for c in value["conversations"]))
        self.assertTrue(all(c["repeat_stage_vector_matches"] == {"initial": True, "update": True}
                            for c in value["conversations"]))

    def test_held_cells_remain_raw_diagnostics_without_reweighting(self):
        cells = audit.diagnostics(self.core)["conversations"]
        held = [c for c in cells if c["comparative_review_hold"]]
        self.assertEqual(len(held), 8)
        self.assertTrue(all(c["score_use"] == "review_held_raw_diagnostic_only" for c in held))
        self.assertTrue(all(c["first"] for c in held))
        self.assertTrue(all(c["review_issues"] for c in held))

    def test_no_answer_explanation_or_pooled_means(self):
        value = audit.diagnostics(self.core)
        encoded = json.dumps(value)
        for text in ("New fixture", "Imported fixture", "response_evidence", "explanation",
                     "mean_score", "ranking"):
            self.assertNotIn(text, encoded)

    def test_missing_repeat_is_null_not_zero_or_first_score(self):
        core = deepcopy(self.core)
        row = next(r for r in core.rows if r["kind"] == "judge" and r["block"] == "development"
                   and r["repeat"] and r["stage"] == "update")
        del core.judgments[panel.workflow.judgment_key(row)]
        cell = audit.diagnostics(core)["conversations"][0]
        self.assertIsNotNone(cell["first"])
        self.assertIsNone(cell["repeat"])
        self.assertEqual(cell["repeat_missing_reason"], "judgment_pair_missing")
        self.assertIsNone(cell["repeat_stage_vector_matches"])

    def test_gate_failure_suppresses_all_candidate_scores(self):
        with patch.object(self.core, "gate", return_value={"pass": False}):
            value = audit.diagnostics(self.core)
        self.assertTrue(all(c["first"] is None and c["repeat"] is None for c in value["conversations"]))
        self.assertTrue(all(c["first_missing_reason"] == "control_gate_not_passed" for c in value["conversations"]))
        self.assertTrue(all(c["diagnostic"] for c in value["controls"]))

    def test_scoring_reuses_frozen_combine_exactly(self):
        row = next(r for r in self.core.rows if r["kind"] == "judge" and r["block"] == "development"
                   and not r["repeat"] and r["stage"] == "update")
        initial = self.core.judgments[panel.workflow.judgment_key({**row, "stage": "initial"})]
        update = self.core.judgments[panel.workflow.judgment_key(row)]
        _, expected = panel.score.combine(initial, update, self.core.contexts[row["sequence"]]["full"],
            {"version": panel.score.VERSION, **panel.score.ARITHMETIC})
        actual = audit.pair_diagnostic(self.core, row)["scoring"]
        self.assertEqual(actual, {k: expected[k] for k in actual})


class JournalAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve() / "run"
        self.freeze = live.snapshot(ROOT)
        self.protocol = panel.sha256_json(self.freeze)
        self.writer = live.Session(ROOT, self.directory, imports(), self.protocol,
                                   "0.01", mode="offline_fixture")

    def step(self, status=200):
        def expensive(raw):
            raw["usage"] = {"total_input_tokens": 10000, "total_output_tokens": 10000,
                            "total_thought_tokens": 1000, "total_tokens": 21000}
        def connection(host, *, timeout):
            return live.rehearsal._Connection(live.rehearsal.Fixture(
                reply(self.writer.core, expensive), status, {}, None))
        self.writer.step({"gemini": "FIXTURE", "minimax": "FIXTURE"}, connection)

    def test_terminal_threshold_report_is_readonly_and_text_free(self):
        self.step()
        before = {p: p.read_bytes() for p in self.directory.rglob("*") if p.is_file()}
        with patch.object(panel.old.prior, "read_setting") as keys, \
             patch.object(panel.old.prior, "create_tls_connection") as network:
            value = audit.audit(ROOT, self.directory, self.freeze)
        keys.assert_not_called(); network.assert_not_called()
        self.assertEqual(before, {p: p.read_bytes() for p in self.directory.rglob("*") if p.is_file()})
        self.assertEqual(value["terminal"], "spend_threshold_reached")
        self.assertEqual(value["transport_attempts"], 1)
        self.assertEqual(value["live_calls"], 0)
        self.assertEqual(value["answer_stages_present"], 17)
        self.assertEqual(value["first_complete_conversation_judgments"], 0)
        self.assertFalse(value["scope_exhausted"])
        self.assertFalse(value["reporting"]["pooled_model_means"])

    def test_transport_failure_preserves_unknown_cost(self):
        self.step(status=403)
        value = audit.audit(ROOT, self.directory, self.freeze)
        self.assertEqual(value["unknown_charge_attempts"], 1)
        self.assertEqual(value["answer_stages_present"], 16)
        self.assertEqual(value["transport_attempts"], 1)
        self.assertEqual(value["terminal"], "transport_failure_unknown_delivery_or_cost")

    def test_active_prefix_rejected_as_final_report(self):
        with self.assertRaisesRegex(ValueError, "Active or interrupted"):
            audit.audit(ROOT, self.directory, self.freeze)

    def test_tampered_raw_or_freeze_rejected(self):
        self.step()
        with self.assertRaises(ValueError): audit.audit(ROOT, self.directory, {})
        (self.directory / "events/0001/capture/0001.raw.bin").write_bytes(b"{}")
        with self.assertRaises(ValueError): audit.audit(ROOT, self.directory, self.freeze)

    def test_complete_journal_matches_all_cells_and_cost_without_network(self):
        directory = Path(self.temp.name).resolve() / "complete"
        writer = live.Session(ROOT, directory, imports(), self.protocol,
                              "20.00", mode="offline_fixture")
        def connection(host, *, timeout):
            return live.rehearsal._Connection(live.rehearsal.Fixture(reply(writer.core), 200, {}, None))
        while writer.step({"gemini": "FIXTURE", "minimax": "FIXTURE"}, connection) is not None:
            pass
        with patch.object(panel.old.prior, "read_setting") as keys, \
             patch.object(panel.old.prior, "create_tls_connection") as network:
            value = audit.audit(ROOT, directory, self.freeze)
        keys.assert_not_called(); network.assert_not_called()
        self.assertTrue(value["scope_exhausted"])
        self.assertEqual(value["transport_attempts"], 452)
        self.assertEqual(sum(r["count"] for r in value["attempt_counts"]), 452)
        self.assertEqual(value["answer_stages_present"], 144)
        self.assertEqual(value["first_complete_conversation_judgments"], 72)
        self.assertEqual(value["repeat_complete_conversation_judgments"], 72)
        self.assertEqual(value["review_held_conversations"], 8)
        self.assertTrue(value["control_gate"]["pass"])
        self.assertEqual(value["monitoring_estimate_usd"],
                         live.report(writer.core, "offline_fixture", 452)["monitoring_estimate_usd"])


if __name__ == "__main__":
    unittest.main()
