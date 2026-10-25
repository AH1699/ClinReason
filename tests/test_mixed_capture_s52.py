"""Supplied-byte crash/replay fixtures; no network, credentials or medical claims."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mixed_capture_s52 as run
from tests.test_mixed_panel_s51 import ROOT, imports, reply


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = imports()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / "journal"

    def new(self, **kw):
        return run.Journal(ROOT, self.path, self.records, mode="offline_fixture", **kw)

    def one(self, journal, transform=None):
        self.assertIsNotNone(journal.prepare())
        journal.record(reply(journal._core, transform))

    def replay(self):
        return run.replay(ROOT, self.path)

    def edit(self, name, transform):
        path = self.path / name
        value = json.loads(path.read_bytes())
        transform(value)
        # Deliberate test-only tampering, never a production repair path.
        path.write_bytes(run.guard._json_bytes(value))

    def test_full_452_request_reconstruction_and_readonly_replay(self):
        journal = self.new()
        while journal.prepare() is not None:
            journal.record(reply(journal._core))
        before = {str(p): p.read_bytes() for p in self.path.rglob("*") if p.is_file()}
        rebuilt = self.replay()
        self.assertEqual(rebuilt["replay_status"], "complete_verified")
        self.assertEqual(rebuilt["report"], journal._core.report())
        self.assertEqual(rebuilt["report"]["simulated_attempts"], 452)
        self.assertEqual(rebuilt["report"]["answer_stages_present"], 144)
        self.assertEqual(len(rebuilt["report"]["conversations"]), 72)
        self.assertEqual(sum(c["comparative_review_hold"] for c in rebuilt["report"]["conversations"]), 8)
        self.assertEqual(rebuilt["events"], 453)
        self.assertFalse(rebuilt["resume_allowed"])
        self.assertFalse(rebuilt["report"]["numeric_scores"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.path.rglob("*") if p.is_file()})

    def test_fresh_only_no_reopening(self):
        self.new()
        with self.assertRaises(FileExistsError):
            self.new()

    def test_no_live_mode_or_callable(self):
        with self.assertRaises(ValueError):
            run.Journal(ROOT, self.path, self.records, mode="live")
        journal = self.new()
        journal.prepare()
        with self.assertRaises(ValueError):
            journal.record(lambda: b"{}")
        with self.assertRaises(ValueError):
            journal.record(b"{}")

    def test_pending_double_dispatch_and_double_reply_refused(self):
        journal = self.new()
        journal.prepare()
        with self.assertRaises(ValueError):
            journal.prepare()
        journal.record(reply(journal._core))
        with self.assertRaises(ValueError):
            journal.record(b"{}")

    def test_all_interruption_file_boundaries_and_poisoned_writer(self):
        original = run.guard._write_exclusive
        for filename in ("reservation.json", "payload.json", "raw.bin", "receipt.json", "result.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as folder:
                self.path = Path(folder).resolve() / "journal"
                journal = self.new()
                def broken(path, raw):
                    if path.name == filename:
                        raise OSError("injected disk failure")
                    original(path, raw)
                with patch.object(run.guard, "_write_exclusive", side_effect=broken):
                    with self.assertRaises(OSError):
                        journal.prepare()
                        journal.record(reply(journal._core))
                with self.assertRaises(ValueError):
                    journal.prepare()
                reconstructed = self.replay()
                self.assertEqual(reconstructed["report"]["simulated_attempts"], int(filename == "result.json"))
                self.assertFalse(reconstructed["resume_allowed"])
                self.assertNotEqual(reconstructed["replay_status"], "complete_verified")

    def test_raw_without_receipt_is_not_parsed(self):
        journal = self.new(); self.one(journal)
        (self.path / "events/0001/result.json").unlink()
        (self.path / "events/0001/receipt.json").unlink()
        self.assertEqual(self.replay()["report"]["simulated_attempts"], 0)

    def test_known_cost_rejection_closes_lane_and_preserves_denominator(self):
        journal = self.new()
        self.one(journal, lambda raw: raw.update(status="incomplete"))
        self.one(journal)
        rebuilt = self.replay()
        self.assertEqual(rebuilt["report"], journal._core.report())
        self.assertEqual(rebuilt["report"]["outcomes"]["rejected"], 1)
        self.assertEqual(rebuilt["report"]["outcomes"]["skipped"], 1)
        self.assertEqual(len(rebuilt["report"]["conversations"]), 72)

    def test_unknown_usage_stops_without_retry(self):
        journal = self.new()
        self.one(journal, lambda raw: raw.pop("usage"))
        self.assertIsNone(journal.prepare())
        rebuilt = self.replay()
        self.assertEqual(rebuilt["replay_status"], "complete_verified")
        self.assertEqual(rebuilt["report"]["terminal"], "unknown_charge")

    def test_threshold_and_last_request_overrun(self):
        journal = self.new(fixture_threshold_usd="0.01")
        self.one(journal, lambda raw: raw["usage"].update(total_input_tokens=1000,
            total_output_tokens=8000, total_thought_tokens=22, total_tokens=9022))
        self.assertEqual(self.replay()["report"]["terminal"], "spend_threshold_reached")

    def test_byte_payload_context_accounting_and_manifest_tamper_rejected(self):
        files = [("events/0001/payload.json", lambda x: x.update(model="different")),
                 ("events/0001/reservation.json", lambda x: x.update(context_sha256="0"*64)),
                 ("events/0001/receipt.json", lambda x: x.update(bytes=0)),
                 ("events/0001/result.json", lambda x: x.update(monitored_ticks=0)),
                 ("manifest.json", lambda x: x.update(live_calls=1)),
                 ("imports.json", lambda x: x[0]["result"].update(text="changed"))]
        for filename, change in files:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as folder:
                self.path = Path(folder).resolve() / "journal"
                journal = self.new(); self.one(journal)
                self.edit(filename, change)
                with self.assertRaises(ValueError):
                    self.replay()

    def test_duplicate_json_key_rejected(self):
        self.new()
        (self.path / "manifest.json").write_bytes(b'{"version":1,"version":2}')
        with self.assertRaises(ValueError):
            self.replay()

    def test_orphan_and_gapped_events_rejected(self):
        journal = self.new(); self.one(journal)
        (self.path / "events/0001").rename(self.path / "events/0002")
        with self.assertRaises(ValueError):
            self.replay()

    def test_after_stop_or_incomplete_tail_rejected(self):
        journal = self.new(); journal.prepare()
        (self.path / "events/0002").mkdir()
        with self.assertRaises(ValueError):
            self.replay()

    def test_symlink_rejected(self):
        journal = self.new(); self.one(journal)
        (self.path / "alias").symlink_to(self.path / "manifest.json")
        with self.assertRaises(ValueError):
            self.replay()

    def test_missing_receipt_with_downstream_result_rejected(self):
        journal = self.new(); self.one(journal)
        (self.path / "events/0001/receipt.json").unlink()
        with self.assertRaises(ValueError):
            self.replay()

    def test_failed_control_gate_captures_skips_and_completes(self):
        journal = self.new()
        while journal.prepare() is not None:
            raw = reply(journal._core)
            if journal._core.pending["kind"] == "judge":
                obj = json.loads(raw); obj["status"] = "incomplete"; raw = json.dumps(obj).encode()
            journal.record(raw)
        rebuilt = self.replay()
        self.assertFalse(rebuilt["report"]["control_gate"]["pass"])
        self.assertEqual(rebuilt["replay_status"], "complete_verified")
        self.assertEqual(rebuilt["report"]["simulated_attempts"], 129)
        self.assertEqual(rebuilt["report"]["outcomes"]["skipped"], 323)

    def test_saved_bank_requires_actual_verification_and_no_supplied_override(self):
        with self.assertRaises(ValueError):
            self.new(source_mode="verified_saved_bank")
        value = {"bank": {"answers": deepcopy(self.records)}, "source_sha256": "a"*64,
                 "source_protocol_sha256": "b"*64, "bank_sha256": "c"*64}
        with patch.object(run.panel, "verified_source", return_value=value) as verify:
            journal = run.Journal(ROOT, self.path, mode="offline_fixture", source_mode="verified_saved_bank")
            self.one(journal)
            self.assertTrue(self.replay()["source"]["historical_provenance_verified"])
            self.assertEqual(verify.call_count, 2)

    def test_unresolved_reservation_is_visible_and_not_a_free_completed_request(self):
        journal = self.new(); journal.prepare()
        rebuilt = self.replay()
        self.assertTrue(rebuilt["unresolved_fixture_reservation"])
        self.assertEqual(rebuilt["report"]["simulated_attempts"], 0)
        self.assertEqual(rebuilt["replay_status"], "interrupted_unconfirmed_reply")

    def test_raw_byte_tampering_rejected(self):
        journal = self.new(); self.one(journal)
        path = self.path / "events/0001/raw.bin"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError): self.replay()

    def test_event_after_unknown_charge_stop_rejected(self):
        journal = self.new(); self.one(journal, lambda raw: raw.pop("usage"))
        (self.path / "events/0002").mkdir()
        with self.assertRaises(ValueError): self.replay()

    def test_saved_terminal_report_tampering_rejected(self):
        journal = self.new(); self.one(journal, lambda raw: raw.pop("usage"))
        self.edit("report.json", lambda x: x.update(simulated_attempts=0))
        with self.assertRaises(ValueError): self.replay()

    def test_parser_failure_retains_complete_bytes_and_blocks_another_reply(self):
        journal = self.new(); journal.prepare(); raw = reply(journal._core)
        with patch.object(journal._core, "record", side_effect=RuntimeError("local parser fixture")):
            with self.assertRaises(RuntimeError): journal.record(raw)
        with self.assertRaises(ValueError): journal.record(raw)
        rebuilt = self.replay()
        self.assertEqual(rebuilt["replay_status"], "captured_reply_reconstructed_without_result")
        self.assertEqual(rebuilt["report"]["simulated_attempts"], 1)
        self.assertFalse(rebuilt["unresolved_fixture_reservation"])


if __name__ == "__main__":
    unittest.main()
