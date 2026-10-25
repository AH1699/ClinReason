from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mixed_transport_s53 as run
from tests.test_mixed_panel_s51 import ROOT, imports, reply


def next_fixture(writer, transform=None):
    core = writer.scheduler._core
    row = next((r for r in core.rows[core.index:] if not core.skip_reason(r)), None)
    if row is None:
        return run.Fixture()
    context = run.panel.request_context(ROOT, row, core.catalog, core.controls, core.answers)
    return run.Fixture(reply(SimpleNamespace(pending=row, contexts={row["sequence"]: context}), transform))


class MixedTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = imports()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / "run"

    def new(self, **kw):
        return run.Rehearsal(ROOT, self.path, self.records, mode="offline_transport_fixture", **kw)

    def replay(self):
        return run.replay(ROOT, self.path)

    def test_complete_mixed_panel_transport_and_replay(self):
        writer = self.new()
        while writer.step(next_fixture(writer)) is not None:
            pass
        before = {str(p): run.journal.digest(p.read_bytes()) for p in self.path.rglob("*") if p.is_file()}
        value = self.replay()
        self.assertEqual(value["sealed_bridges"], 452)
        self.assertEqual(value["forwarded_replies"], 452)
        self.assertIsNone(value["incomplete_tail"])
        self.assertEqual(value["scheduler"]["replay_status"], "complete_verified")
        self.assertEqual(value["scheduler"]["report"], writer.scheduler._core.report())
        self.assertEqual(value["scheduler"]["report"]["answer_stages_present"], 144)
        self.assertEqual(before, {str(p): run.journal.digest(p.read_bytes()) for p in self.path.rglob("*") if p.is_file()})

    def test_no_live_mode_external_factory_or_credential(self):
        with self.assertRaises(ValueError):
            run.Rehearsal(ROOT, self.path, self.records, mode="live")
        writer = self.new()
        with self.assertRaises(ValueError): writer.step(lambda: b"{}")
        with self.assertRaises(TypeError): writer.step(run.Fixture(), credential="secret")
        with self.assertRaises(TypeError): writer.step(run.Fixture(), connection_factory=lambda: None)
        self.assertEqual(writer.scheduler._event, 0)

    def test_reservations_and_payloads_precede_simulated_connection(self):
        writer = self.new(); original = run._Connection
        def factory(fixture):
            self.assertTrue((self.path / "scheduler/events/0001/reservation.json").exists())
            self.assertTrue((self.path / "captures/0001/transport/0001.attempt.json").exists())
            self.assertTrue((self.path / "captures/0001/transport/0001.payload.json").exists())
            return original(fixture)
        with patch.object(run, "_Connection", side_effect=factory): writer.step(next_fixture(writer))
        self.assertEqual(writer.last_connection.requests[0][0], "POST")
        self.assertTrue(writer.last_connection.closed)
        self.assertTrue(writer.last_connection.response.closed)

    def test_http_error_with_valid_answer_body_never_enters_scheduler(self):
        for status in (302, 403, 429, 500):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                self.path = Path(folder).resolve() / "run"; writer = self.new()
                writer.step(run.Fixture(next_fixture(writer).body, status=status))
                value = self.replay()
                self.assertEqual(value["transport_stop"]["category"], "http_status")
                self.assertEqual(value["forwarded_replies"], 0)
                self.assertEqual(value["scheduler"]["report"]["answer_stages_present"], 16)
                self.assertEqual(value["unforwarded_unresolved_attempts"], 1)
                self.assertIsNone(writer.step(run.Fixture()))
                self.assertEqual(len(writer.last_connection.requests), 1)

    def test_transport_faults_retain_partial_bytes_and_stop(self):
        for fault in ("connect_timeout", "response_timeout", "read_timeout", "incomplete_read"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                self.path = Path(folder).resolve() / "run"; writer = self.new()
                writer.step(run.Fixture(b"prefix", fault=fault))
                value = self.replay()
                self.assertEqual(value["forwarded_replies"], 0)
                self.assertEqual(value["unforwarded_unresolved_attempts"], 1)
                if fault in ("read_timeout", "incomplete_read"):
                    self.assertEqual((self.path / "captures/0001/transport/0001.raw.bin").read_bytes(), b"prefix")
                self.assertIsNone(writer.step(run.Fixture()))

    def test_length_mismatch_encoding_and_invalid_status_stop(self):
        for fixture in (run.Fixture(b"{}", headers={"Content-Length": "99"}),
                        run.Fixture(b"{}", headers={"Content-Encoding": "gzip"}), run.Fixture(status=99)):
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as folder:
                self.path = Path(folder).resolve() / "run"; writer = self.new(); writer.step(fixture)
                self.assertIsNotNone(self.replay()["transport_stop"])

    def test_deadline_and_response_size_limits(self):
        writer = self.new()
        with patch.object(run.capture.time, "monotonic", side_effect=[0, 1801, 1802]):
            result = writer.step(run.Fixture(b"x"))
        self.assertEqual(result["category"], "response_deadline")
        self.assertEqual(self.replay()["forwarded_replies"], 0)
        with tempfile.TemporaryDirectory() as folder:
            self.path = Path(folder).resolve() / "run"; writer = self.new()
            result = writer.step(run.Fixture(b"x" * (8388608 + 2)))
            self.assertEqual(result["category"], "response_size_limit")
            self.assertEqual((self.path / "captures/0001/transport/0001.raw.bin").stat().st_size, 8388609)
            self.assertEqual(self.replay()["forwarded_replies"], 0)

    def test_interrupt_retains_raw_and_cannot_restart(self):
        writer = self.new()
        with self.assertRaises(KeyboardInterrupt): writer.step(run.Fixture(b"prefix", fault="interrupt"))
        with self.assertRaises(ValueError): writer.step(run.Fixture())
        value = self.replay()
        self.assertEqual(value["incomplete_tail"], "interrupted_before_bridge_record")
        self.assertEqual((self.path / "captures/0001/transport/0001.raw.bin").read_bytes(), b"prefix")

    def test_known_cost_invalid_answer_closes_lane_then_other_model_continues(self):
        writer = self.new(); writer.step(next_fixture(writer, lambda raw: raw.update(status="incomplete")))
        writer.step(next_fixture(writer))
        value = self.replay()
        self.assertEqual(value["forwarded_replies"], 2)
        self.assertEqual(value["scheduler"]["report"]["outcomes"]["skipped"], 1)
        self.assertEqual(value["scheduler"]["report"]["outcomes"]["rejected"], 1)

    def test_malformed_body_and_unknown_usage_stop_at_scheduler(self):
        for transform in (None, lambda raw: raw.pop("usage")):
            with tempfile.TemporaryDirectory() as folder:
                self.path = Path(folder).resolve() / "run"; writer = self.new()
                writer.step(run.Fixture(b"not json") if transform is None else next_fixture(writer, transform))
                value = self.replay()
                self.assertEqual(value["scheduler"]["report"]["terminal"], "unknown_charge")
                self.assertEqual(value["forwarded_replies"], 1)
                self.assertIsNone(writer.step(run.Fixture()))

    def test_threshold_overrun_stops_new_transport(self):
        writer = self.new(fixture_threshold_usd="0.01")
        writer.step(next_fixture(writer, lambda raw: raw["usage"].update(total_input_tokens=1000,
            total_output_tokens=8000, total_thought_tokens=22, total_tokens=9022)))
        self.assertEqual(self.replay()["scheduler"]["report"]["terminal"], "spend_threshold_reached")
        self.assertIsNone(writer.step(run.Fixture()))

    def test_each_write_failure_poisoned_without_retry(self):
        original = run.guard._write_exclusive
        for filename in ("0001.attempt.json", "0001.payload.json", "0001.accounting.json", "bridge.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as folder:
                self.path = Path(folder).resolve() / "run"; writer = self.new()
                def fail(path, body):
                    if path.name == filename: raise OSError("simulated disk failure")
                    return original(path, body)
                with patch.object(run.guard, "_write_exclusive", side_effect=fail):
                    with self.assertRaises(OSError): writer.step(next_fixture(writer))
                with self.assertRaises(ValueError): writer.step(run.Fixture())
                rebuilt = self.replay()
                self.assertIsNotNone(rebuilt["incomplete_tail"])
                self.assertEqual(rebuilt["unresolved_bridge_entries"], 1)
                self.assertEqual(rebuilt["unforwarded_unresolved_attempts"], int(filename != "bridge.json"))
                if filename == "bridge.json":
                    self.assertEqual(rebuilt["scheduler"]["report"]["simulated_attempts"], 1)

    def test_capture_tamper_and_orphan_rejected(self):
        writer = self.new(); writer.step(next_fixture(writer))
        raw = self.path / "captures/0001/transport/0001.raw.bin"
        original = raw.read_bytes(); raw.write_bytes(original + b" ")
        with self.assertRaises(ValueError): self.replay()
        raw.write_bytes(original)
        (self.path / "captures/0002").mkdir()
        with self.assertRaises(ValueError): self.replay()

    def test_fake_credentials_headers_and_exception_text_not_logged(self):
        writer = self.new(); fixture = next_fixture(writer)
        writer.step(run.Fixture(fixture.body, headers={"Set-Cookie": "secret-cookie", "Location": "https://evil.invalid"}))
        for path in self.path.rglob("*"):
            if path.is_file():
                for token in (b"S53-FIXTURE-ONLY", b"secret-cookie", b"evil.invalid"):
                    self.assertNotIn(token, path.read_bytes())

    def test_no_restart_or_linked_capture(self):
        writer = self.new()
        with self.assertRaises(FileExistsError): self.new()
        writer.step(next_fixture(writer))
        (self.path / "alias").symlink_to(self.path / "manifest.json")
        with self.assertRaises(ValueError): self.replay()

    def test_policy_retains_all_cells_and_holds_no_model_mean(self):
        result = run.policy.reporting_manifest(ROOT)
        self.assertEqual(len(result["conversations"]), 72)
        self.assertEqual(sum(c["comparative_review_hold"] for c in result["conversations"]), 8)
        self.assertFalse(result["reporting"]["pooled_model_means"])
        self.assertFalse(result["reporting"]["cell_removal"])
        self.assertFalse(result["computed_scores"])

    def test_policy_cannot_grant_live_allowance_or_change_judge_cap(self):
        original = run.panel.read_json
        for section, key, value in (("authorization", "live_call_allowance", 1),
                                    ("judge", "max_output_tokens", 8192),
                                    ("reporting", "pooled_model_means", True)):
            changed = deepcopy(run.policy.policy(ROOT)); changed[section][key] = value
            def read(path):
                return changed if path == ROOT / run.policy.PATH else original(path)
            with patch.object(run.panel, "read_json", side_effect=read):
                with self.assertRaises(ValueError): run.policy.policy(ROOT)


if __name__ == "__main__": unittest.main()
