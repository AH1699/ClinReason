"""Offline readout fixtures, not provider calls or clinical ground truth."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_standalone_s63 as audit

ROOT = Path(__file__).resolve().parents[1]
live = audit.live


class ReadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = live.Core(ROOT, "20.00")
        while not cls.core.terminal:
            fixture = live.previous.next_fixture(cls.core)
            request = cls.core.prepare()
            if request is None:
                break
            raw = live.capture.strict_json(fixture.body)
            c = request["context"]
            account = live.capture.account(raw, cls.core.model_specs[c["provider"], c["model"]], c["payload"])
            cls.core.consume({"category": "accepted", "accepted": True, "result": cls.core.decode(raw), "accounting": account}, fixture.body)
        manifest = live.pilot.verify(ROOT)
        cls.families = {f["family_id"]: f for f in manifest["families"]}
        cls.report = live.report(cls.core, "offline_fixture")
        cls.cells = [audit.conversation(c, cls.families) for c in cls.report["conversations"]]

    def test_all_64_cells_and_eight_families_remain_held(self):
        values = audit.family_readout(self.cells)
        self.assertEqual(len(values), 8)
        self.assertEqual(sum(f["expected_cells"] for f in values), 64)
        self.assertEqual(sum(f["review_held_cells"] for f in values), 64)
        self.assertTrue(all(f["complete_repeat_pairs"] == 8 for f in values))

    def test_missing_first_is_not_zero_or_replaced_by_repeat(self):
        cell = deepcopy(self.cells[0])
        cell["first"]["score"] = None
        value = audit.phase_counts([cell], "first")
        self.assertEqual(value["missing_conversations"], 1)
        self.assertIsNone(value["point_range"])
        self.assertEqual(audit.phase_counts([cell], "repeat")["complete_conversations"], 1)
        self.assertIsNone(audit.repeat_comparison(cell))

    def test_interval_not_point_or_perfect_score(self):
        cell = deepcopy(self.cells[0])
        cell["first"]["score"].update(point_score=None, provisional_pass=None, criterion_score_interval=[60,100])
        value = audit.phase_counts([cell], "first")
        self.assertEqual((value["interval_only"], value["point_scores"], value["exactly_100"]), (1,0,0))
        self.assertIsNone(audit.repeat_comparison(cell)["point_delta_repeat_minus_first"])

    def test_changed_scores_and_vectors_are_separate(self):
        cell = deepcopy(self.cells[0])
        cell["first"]["score"]["point_score"] = 80
        cell["repeat"]["score"]["point_score"] = 90
        cell["repeat"]["judgments"]["update"]["criterion_assessments"][0]["status"] = "missed"
        value = audit.family_readout([cell])[0]
        self.assertEqual(value["maximum_absolute_repeat_gap"], 10)
        self.assertEqual(value["matching_stage_vectors"], 1)
        self.assertEqual(value["exact_point_repeats"], 0)

    def test_future_text_fields_do_not_export(self):
        cell = deepcopy(self.report["conversations"][0])
        cell["extra_private"] = "PRIVATE SENTINEL"
        cell["first"]["score"]["future_explanation"] = "PRIVATE SENTINEL"
        judgment = cell["first"]["judgments"]["initial"]
        judgment["extra_private"] = "PRIVATE SENTINEL"
        judgment["criterion_assessments"][0]["response_evidence"] = "PRIVATE SENTINEL"
        text = json.dumps(audit.conversation(cell, self.families))
        for marker in ("PRIVATE SENTINEL", "response_evidence", "rationale", "new_fact", "overlap_note"):
            self.assertNotIn(marker, text)

    def test_partial_stage_remains_without_conversation_total(self):
        cell = deepcopy(self.cells[0])
        cell["first"]["score"] = None
        cell["first"]["judgments"]["update"] = None
        value = audit.phase_counts([cell], "first")
        self.assertEqual(value["accepted_stage_judgments"], 1)
        self.assertEqual(value["missing_conversations"], 1)

    def test_control_changes_visible_and_error_order_not_a_change(self):
        value = deepcopy(self.report["control_readout"])
        repeat = next(r for r in value["stage_results"] if r["job_id"].startswith("control_repeat"))
        first = next(r for r in value["stage_results"]
                     if r["job_id"] == repeat["job_id"].replace("control_repeat", "control_first", 1))
        first["critical_errors"] = [{"stage_id": "initial", "error_id": e, "severity": 3}
                                    for e in ("fixture-a", "fixture-b")]
        repeat["critical_errors"] = list(reversed(first["critical_errors"]))
        self.assertEqual(audit.control_readout(value, self.core.control_records)["repeat_vector_changes"], [])
        repeat["criterion_statuses"][0] = "partial"
        result = audit.control_readout(value, self.core.control_records)
        self.assertEqual(len(result["repeat_vector_changes"]), 1)
        self.assertEqual(len(result["stage_results"]), 96)
        self.assertNotIn("response_evidence", json.dumps(result))

    def test_clinical_comparison_and_score_fitting_not_added(self):
        text = json.dumps(audit.family_readout(self.cells))
        for marker in ("mean_score", "ranking", "adjusted_score"):
            self.assertNotIn(marker, text)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / "run"
        self.freeze = live.snapshot(ROOT)
        self.writer = live.Session(ROOT, self.path, mode="offline_fixture")

    def stop(self, status=403):
        self.writer.step(live.previous.Fixture(b"{}", status=status))

    def test_terminal_audit_readonly_no_keys_or_network(self):
        self.stop()
        before = audit.tree_hash(ROOT, self.path)
        with patch.object(live, "read_setting") as keys, patch.object(live, "tls") as network:
            value = audit.audit(ROOT, self.path, self.freeze)
        keys.assert_not_called(); network.assert_not_called()
        self.assertEqual(before, audit.tree_hash(ROOT, self.path))
        self.assertEqual(value["source_journal_sha256"], before)
        self.assertEqual(value["execution"]["unknown_cost_attempts"], 1)
        self.assertEqual(value["execution"]["unattempted_jobs"], 479)
        self.assertEqual(value["new_provider_calls_by_audit"], 0)
        self.assertEqual(len(value["conversations"]), 64)
        self.assertEqual(value["answer_language_screen"]["missing_or_rejected_turns"], 128)

    def test_active_prefix_refused_as_terminal_report(self):
        self.writer.step(live.previous.next_fixture(self.writer.core))
        with self.assertRaises(ValueError):
            audit.audit(ROOT, self.path, self.freeze)

    def test_accepted_candidate_language_denominator_replayed(self):
        for _ in range(224):  # 96 controls, then 128 fabricated candidate turns.
            self.writer.step(live.previous.next_fixture(self.writer.core))
        self.stop()
        before = audit.tree_hash(ROOT, self.path)
        value = audit.audit(ROOT, self.path, self.freeze)
        self.assertEqual(value["answer_language_screen"]["checked_accepted_turns"], 128)
        self.assertEqual(value["answer_language_screen"]["missing_or_rejected_turns"], 0)
        self.assertFalse(value["answer_language_screen"]["score_adjustments"])
        self.assertEqual(sum(len(c["answer_stages_present"]) for c in value["conversations"]), 128)
        self.assertEqual(before, audit.tree_hash(ROOT, self.path))

    def test_bad_freeze_refused(self):
        self.stop()
        with self.assertRaises(ValueError):
            audit.audit(ROOT, self.path, {})

    def test_tampering_refused(self):
        self.stop()
        (self.path / "events/0001/transport/0001.raw.bin").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            audit.audit(ROOT, self.path, self.freeze)

    def test_mutating_journal_during_readout_refused(self):
        self.stop()
        with patch.object(audit, "tree_hash", side_effect=["before", "after"]), self.assertRaises(ValueError):
            audit.audit(ROOT, self.path, self.freeze)

    def test_public_export_contains_no_response_or_approval_text(self):
        self.stop()
        text = json.dumps(audit.audit(ROOT, self.path, self.freeze))
        for marker in ("response_evidence", "rationale", "authorization_evidence", "approved_by", "new_fact", "overlap_note"):
            self.assertNotIn(marker, text)


class LanguageTests(unittest.TestCase):
    def test_english_in_chinese_turn_flagged_without_exporting_text(self):
        text = "Words about a response that is clearly written in English and sufficiently long to trigger the existing conservative script mismatch threshold."
        value = audit.language_flag(text, "zh-Hans")
        self.assertEqual(value["reason"], "zh_expected_english_script_dominant")
        self.assertNotIn(text, json.dumps(value))

    def test_chinese_in_english_turn_flagged(self):
        self.assertEqual(audit.language_flag("这是一段用于软件测试的中文文字，内容不用于任何临床判断。", "en")["reason"],
                         "en_expected_han_script_dominant")

    def test_short_or_matching_scripts_not_flagged_but_not_approved(self):
        self.assertIsNone(audit.language_flag("Short fixture", "zh-Hans"))
        self.assertIsNone(audit.language_flag("这是一段中文软件测试文字。", "zh-Hans"))
        self.assertIsNone(audit.language_flag("This is an English software test fixture with enough Latin words.", "en"))

    def test_empty_or_unsupported_language_rejected(self):
        for text, language in (("", "en"), (None, "en"), ("fixture", "unknown")):
            with self.assertRaises(ValueError):
                audit.language_flag(text, language)


if __name__ == "__main__":
    unittest.main()
