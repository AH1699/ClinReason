"""Offline fixtures only. No model performance or clinical ground truth."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_judge_panel_s58 as audit
from tests.test_judge_panel_s57 import advance, bad_quote
from tests.test_judge_saved_bank_s56 import fixture_bank
from tests.test_mixed_panel_s51 import reply

ROOT = Path(__file__).resolve().parents[1]
live = audit.live


class ReadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = fixture_bank()
        cls.core = advance(live.engine.Core(ROOT, cls.bank, "5.00"))
        cls.cells = live.engine.report(cls.core, "offline_fixture", 324)["case_diagnostics"]

    def test_all_families_and_held_cells_remain_visible(self):
        families = audit.family_readout(self.cells)
        self.assertEqual(len(families), 9)
        self.assertEqual(sum(f["expected_cells"] for f in families), 72)
        self.assertEqual(sum(f["review_held_cells"] for f in families), 8)
        self.assertTrue(all(f["paired_first_repeat"] == 8 for f in families))
        self.assertTrue(all(f["exact_point_repeats"] == 8 for f in families))

    def test_missing_is_not_a_zero_or_repeat_substitute(self):
        cell = deepcopy(self.cells[0]); cell["first"] = None
        value = audit.family_readout([cell])[0]
        self.assertEqual(value["first"]["missing_pairs"], 1)
        self.assertIsNone(value["first"]["point_range"])
        self.assertEqual(value["repeat"]["complete_pairs"], 1)
        self.assertIsNone(audit.repeat_comparison(cell))

    def test_unclear_interval_not_counted_as_point_or_ceiling(self):
        cell = deepcopy(self.cells[0]); score = cell["first"]["scoring"]
        score.update(point_score=None, provisional_pass=None, criterion_score_interval=[60, 100])
        value = audit.pass_counts([cell], "first")
        self.assertEqual((value["interval_only_pairs"], value["point_scores"], value["exactly_100"]), (1, 0, 0))
        self.assertEqual(value["provisional_pass_unresolved"], 1)
        self.assertIsNone(audit.repeat_comparison(cell)["point_delta_repeat_minus_first"])

    def test_score_and_vector_changes_remain_separate(self):
        cell = deepcopy(self.cells[0])
        cell["first"]["scoring"]["point_score"] = 80
        cell["repeat"]["scoring"]["point_score"] = 92.5
        cell["repeat_stage_vector_matches"]["update"] = False
        value = audit.family_readout([cell])[0]
        self.assertEqual(value["maximum_absolute_repeat_gap"], 12.5)
        self.assertEqual(value["exact_point_repeats"], 0)
        self.assertEqual(value["repeat_stage_vectors_matched"], 1)
        self.assertEqual(value["repeat_stage_vectors_compared"], 2)

    def test_no_private_text_or_model_aggregate(self):
        cell = deepcopy(self.cells[0])
        cell["private_future_field"] = "PRIVATE SENTINEL"
        cell["first"]["scoring"]["future_explanation"] = "PRIVATE SENTINEL"
        text = json.dumps([audit.family_readout([cell]), audit.repeat_comparison(cell)])
        for marker in ("PRIVATE SENTINEL", "response_evidence", "mean_score", "ranking"):
            self.assertNotIn(marker, text)

    def test_rejected_first_has_no_complete_pair(self):
        core = advance(live.engine.Core(ROOT, self.bank, "5.00"), 36)
        core.prepare(); core.record(reply(core, bad_quote)); advance(core)
        cells = live.engine.report(core, "offline_fixture", 323)["case_diagnostics"]
        first = audit.family_readout(cells)[0]
        self.assertEqual(first["first"]["complete_pairs"], 7)
        self.assertEqual(first["repeat"]["complete_pairs"], 7)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name).resolve() / "run"
        self.freeze = live.snapshot(ROOT)
        self.writer = live.Session(ROOT, self.directory, fixture_bank(), live.panel.sha256_json(self.freeze),
                                   "0.01", mode="offline_fixture")

    def step(self, status=200):
        def expensive(raw):
            raw["usage"] = {"total_input_tokens": 10000, "total_output_tokens": 10000,
                            "total_thought_tokens": 1000, "total_tokens": 21000}
        def connection(host, *, timeout):
            return live.rehearsal._Connection(live.rehearsal.Fixture(reply(self.writer.core, expensive), status, {}, None))
        self.writer.step("FIXTURE", connection)

    def test_terminal_readout_is_readonly_without_network_or_keys(self):
        self.step(); before = live.saved.tree_hash(self.directory)
        with patch.object(live.panel.old.prior, "read_setting") as keys, \
                patch.object(live.panel.old.prior, "create_tls_connection") as network:
            result = audit.audit(ROOT, self.directory, self.freeze)
        keys.assert_not_called(); network.assert_not_called()
        self.assertEqual(result["source_journal_sha256"], before)
        self.assertEqual(live.saved.tree_hash(self.directory), before)
        self.assertEqual(result["replay"]["terminal"], "spend_threshold_reached")
        self.assertEqual(result["schedule_disposition_counts"], {"accepted": 1, "unattempted": 323})
        self.assertEqual(result["new_provider_calls_by_audit"], 0)

    def test_transport_cost_stays_unknown(self):
        self.step(status=403)
        result = audit.audit(ROOT, self.directory, self.freeze)
        self.assertEqual(result["replay"]["unknown_charge_attempts"], 1)
        self.assertEqual(result["replay"]["transport_attempts"], 1)

    def test_active_prefix_and_bad_freeze_not_reported_as_final(self):
        with self.assertRaises(ValueError): audit.audit(ROOT, self.directory, self.freeze)
        with self.assertRaises(ValueError): audit.audit(ROOT, self.directory, {})

    def test_tampered_capture_rejected(self):
        self.step()
        path = self.directory / "events/0001/capture/0001.raw.bin"
        path.write_bytes(b"{}")
        with self.assertRaises(ValueError): audit.audit(ROOT, self.directory, self.freeze)


if __name__ == "__main__":
    unittest.main()
