"""Offline transport/admission/replay tests. No live credentials or requests."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import judge_live_s57 as run
from tests.test_judge_saved_bank_s56 import fixture_bank
from tests.test_judge_panel_s57 import bad_quote
from tests.test_mixed_panel_s51 import reply

ROOT = Path(__file__).resolve().parents[1]


class AdmissionTests(unittest.TestCase):
    def ready(self):
        spec = run.plan(ROOT)
        self.now = datetime(2026, 10, 27, 1, tzinfo=timezone.utc)
        spec["pricing_verification"]["verified_at"] = "2026-10-27T00:00:00Z"
        freeze = {"test_only": True}
        approval = {"approval_id": str(uuid4()), "run_id": str(uuid4()),
            "protocol_sha256": run.panel.sha256_json(freeze), "approved_at": "2026-10-27T00:30:00Z",
            "expires_at": "2026-10-27T02:00:00Z", "approved_by": "TEST ONLY",
            "authorization_evidence": "Fixture; not real permission", "accept_provider_disclosure": True,
            "accept_reporting_policy": True, "accept_threshold_overrun": True, "accept_paid_calls": True,
            "accept_bounded_format_failure_policy": True}
        return spec, freeze, approval

    def check(self, spec, freeze, approval):
        with patch.object(run, "plan", return_value=spec), patch.object(run, "snapshot", return_value={"test_only": True}):
            return run.validate_authorization(ROOT, freeze, approval, self.now)

    def test_exact_new_protocol_can_be_admitted_only_in_mock(self):
        spec, freeze, approval = self.ready()
        self.assertEqual(self.check(spec, freeze, approval)["plan"]["maximum_attempts"], 324)

    def test_missing_or_old_approval_stops_before_source_keys_network(self):
        with patch.object(run, "verified_source") as source, patch.object(run.panel.old.prior, "read_setting") as keys, \
                patch.object(run.panel.old.prior, "create_tls_connection") as network:
            with self.assertRaises(ValueError): run.run_live(ROOT, {}, {}, str(uuid4()))
            source.assert_not_called(); keys.assert_not_called(); network.assert_not_called()
        spec, freeze, approval = self.ready()
        del approval["accept_bounded_format_failure_policy"]
        with self.assertRaises(ValueError): self.check(spec, freeze, approval)

    def test_all_five_permissions_require_true_boolean(self):
        spec, freeze, approval = self.ready()
        for field in [k for k in approval if k.startswith("accept_")]:
            for value in (False, 1, "yes", None):
                changed = deepcopy(approval); changed[field] = value
                with self.assertRaises(ValueError): self.check(spec, freeze, changed)

    def test_expiry_future_overlong_and_pre_price_approval_rejected(self):
        spec, freeze, approval = self.ready()
        for key, value in (("expires_at", "2026-10-27T01:00:00Z"), ("approved_at", "2026-10-27T01:30:00Z"),
                ("expires_at", "2026-10-29T00:00:00Z"), ("approved_at", "2026-10-26T23:59:00Z")):
            changed = deepcopy(approval); changed[key] = value
            with self.assertRaises(ValueError): self.check(spec, freeze, changed)

    def test_prices_must_be_fresh_exact_and_no_cache_discount(self):
        spec, freeze, approval = self.ready()
        for key, value in (("verified_at", "2026-10-25T00:00:00Z"), ("verified_at", "2026-10-28T00:00:00Z"),
                ("output_per_million", 0.01), ("source", "unverified"), ("cache_discount_used", True), ("evidence_note", "")):
            changed = deepcopy(spec); changed["pricing_verification"][key] = value
            with self.assertRaises(ValueError): self.check(changed, freeze, approval)

    def test_freeze_or_protocol_drift_rejected(self):
        spec, freeze, approval = self.ready()
        with self.assertRaises(ValueError): self.check(spec, {"different": True}, approval)
        approval["protocol_sha256"] = "0" * 64
        with self.assertRaises(ValueError): self.check(spec, freeze, approval)

    def test_plan_scope_threshold_and_unknown_fields_rejected(self):
        original = run.plan(ROOT); read = run.journal.read
        for key, value in (("maximum_attempts", 325), ("maximum_attempts", True), ("maximum_development_format_failures", 4),
                ("new_candidate_calls", 1), ("resume_allowed", True), ("stop_threshold_usd", "NaN"),
                ("stop_threshold_usd", "0.00"), ("stop_threshold_usd", "1.001"), ("unexpected", True)):
            changed = deepcopy(original); changed[key] = value
            with patch.object(run.journal, "read", side_effect=lambda p: changed if p == ROOT / run.PLAN else read(p)):
                with self.assertRaises(ValueError): run.plan(ROOT)

    def test_consumed_approval_cannot_reopen_same_or_new_run(self):
        _, _, approval = self.ready()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve()
            run.consume_approval(path, approval, approval["protocol_sha256"], approval["run_id"])
            with self.assertRaises(FileExistsError): run.consume_approval(path, approval, approval["protocol_sha256"], approval["run_id"])
            with self.assertRaises(ValueError): run.consume_approval(path, approval, approval["protocol_sha256"], str(uuid4()))
            self.assertEqual(run.journal.read(next(path.iterdir()))["version"], run.VERSION)

    def test_live_entry_consumes_before_reading_only_gemini_key(self):
        spec, freeze, approval = self.ready()
        checked = {"protocol_sha256": approval["protocol_sha256"], "plan": spec}
        with tempfile.TemporaryDirectory() as tmp:
            parent, consumed = Path(tmp).resolve() / "runs", Path(tmp).resolve() / "consumed"
            parent.mkdir(); consumed.mkdir()
            def key(path, name, **kwargs):
                self.assertEqual(name, run.panel.old.prior.KEY_NAMES["gemini"])
                self.assertTrue((consumed / (approval["approval_id"] + ".json")).exists())
                raise ValueError("SECRET TEST ERROR")
            with patch.object(run, "validate_authorization", return_value=checked), \
                    patch.object(run, "verified_source", return_value=fixture_bank()), \
                    patch.object(run.panel.old.prior, "_private_path", side_effect=[parent, consumed]), \
                    patch.object(run.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
                    patch.object(run.panel.old.prior, "read_setting", side_effect=key), \
                    patch.object(run.panel.old.prior, "create_tls_connection") as network:
                with self.assertRaises(run.guard.AdmissionBlocked) as caught: run.run_live(ROOT, freeze, approval, approval["run_id"])
                self.assertNotIn("SECRET", str(caught.exception)); network.assert_not_called()

    def test_bad_bank_stops_before_consumption_or_credentials(self):
        spec, freeze, approval = self.ready()
        with patch.object(run, "validate_authorization", return_value={"protocol_sha256": "fixture", "plan": spec}), \
                patch.object(run, "verified_source", side_effect=ValueError("source changed")), \
                patch.object(run, "consume_approval") as consume, patch.object(run.panel.old.prior, "read_setting") as key:
            with self.assertRaises(ValueError): run.run_live(ROOT, freeze, approval, approval["run_id"])
            consume.assert_not_called(); key.assert_not_called()


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.bank = fixture_bank()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / "run"
        self.writer = run.Session(ROOT, self.path, self.bank, "fixture-protocol", "5.00", mode="offline_fixture")
        self.connections = []

    def step(self, transform=None, status=200, fault=None):
        def connection(host, *, timeout):
            self.assertEqual(host, "generativelanguage.googleapis.com")
            event = self.path / "events" / f"{self.writer.event:04d}"
            self.assertTrue((event / "reservation.json").exists())
            self.assertTrue((event / "capture/0001.attempt.json").exists())
            value = run.rehearsal._Connection(run.rehearsal.Fixture(reply(self.writer.core, transform), status, {}, fault))
            self.connections.append(value)
            return value
        return self.writer.step("FIXTURE", connection)

    def replay(self): return run.replay(ROOT, self.path, "fixture-protocol")

    def test_full_324_capture_and_readonly_replay(self):
        while self.step() is not None: pass
        before = run.saved.tree_hash(self.path)
        value = self.replay()
        self.assertEqual(value["transport_attempts"], 324)
        self.assertTrue(value["all_pairs_complete"])
        self.assertFalse(value["interrupted"])
        self.assertEqual(value["live_calls"], 0)
        self.assertEqual(before, run.saved.tree_hash(self.path))

    def test_partial_format_failure_persists_and_does_not_hide_missing_cell(self):
        for _ in range(36): self.step()
        self.step(bad_quote)
        while self.step() is not None: pass
        value = self.replay()
        self.assertEqual(value["transport_attempts"], 323)
        self.assertEqual(value["development_format_failures"], 1)
        self.assertEqual(value["outcomes"], {"accepted": 322, "rejected": 1, "skipped": 1})
        self.assertEqual((value["first_complete_pairs"], value["repeat_complete_pairs"]), (71, 71))
        self.assertIsNone(value["case_diagnostics"][0]["first"])

    def test_three_format_failures_stop_and_replay_counter_matches(self):
        for _ in range(36): self.step()
        for _ in range(3): self.step(bad_quote)
        self.assertIsNone(self.step())
        value = self.replay()
        self.assertEqual(value["terminal"], "development_format_failure_limit")
        self.assertEqual(value["transport_attempts"], 39)
        self.assertEqual(value["development_format_failures"], 3)

    def test_http_failure_with_valid_body_never_counts_judgment(self):
        self.step(status=403)
        value = self.replay()
        self.assertEqual(value["unknown_charge_attempts"], 1)
        self.assertEqual(value["control_gate"]["accepted_records"], 0)
        self.assertIsNone(self.step()); self.assertEqual(len(self.connections), 1)

    def test_timeout_stops_without_retry(self):
        self.step(fault="read_timeout")
        self.assertEqual(self.replay()["unknown_charge_attempts"], 1)
        self.assertIsNone(self.step())

    def test_interrupt_preserves_unknown_cost_and_poisons_writer(self):
        with self.assertRaises(KeyboardInterrupt): self.step(fault="interrupt")
        with self.assertRaises(ValueError): self.step()
        value = self.replay()
        self.assertTrue(value["interrupted"])
        self.assertEqual(value["unknown_charge_attempts"], 1)

    def test_pre_capture_disk_failure_not_counted_as_billed_attempt(self):
        with patch.object(run.capture, "CaptureJournal", side_effect=OSError("disk")), self.assertRaises(OSError): self.step()
        value = self.replay()
        self.assertEqual((value["transport_attempts"], value["unknown_charge_attempts"]), (0, 0))
        self.assertTrue(value["unresolved_request_reservation"])

    def test_unknown_usage_stops_immediately(self):
        self.step(lambda raw: raw.pop("usage"))
        self.assertEqual(self.replay()["unknown_charge_attempts"], 1)
        self.assertIsNone(self.step())

    def test_last_request_overrun_is_recorded_then_stops(self):
        self.writer.core.threshold = 1
        # The durable threshold must match the state used by replay.
        self.path = Path(self.temp.name).resolve() / "tiny"
        self.writer = run.Session(ROOT, self.path, self.bank, "fixture-protocol", "0.01", mode="offline_fixture")
        def expensive(raw):
            raw["usage"] = {"total_input_tokens": 10000, "total_output_tokens": 10000,
                            "total_thought_tokens": 1000, "total_tokens": 21000}
        self.step(expensive)
        value = self.replay()
        self.assertEqual(value["terminal"], "spend_threshold_reached")
        self.assertGreater(float(value["monitoring_estimate_usd"]), 0.01)
        self.assertIsNone(self.step())

    def test_result_write_failure_can_be_inspected_not_resumed(self):
        original = run.journal.write
        def broken(path, value):
            if path.name == "result.json": raise OSError("disk")
            return original(path, value)
        with patch.object(run.journal, "write", side_effect=broken), self.assertRaises(OSError): self.step()
        with self.assertRaises(ValueError): self.step()
        value = self.replay()
        self.assertTrue(value["interrupted"])
        self.assertEqual(value["unknown_charge_attempts"], 0)
        self.assertEqual(value["control_gate"]["accepted_records"], 1)

    def test_raw_tampering_and_reopening_rejected(self):
        self.step()
        with self.assertRaises(FileExistsError): run.Session(ROOT, self.path, self.bank, "fixture-protocol", "5.00", mode="offline_fixture")
        (self.path / "events/0001/capture/0001.raw.bin").write_bytes(b"{}")
        with self.assertRaises(ValueError): self.replay()

    def test_accepted_interpretation_tamper_rejected_even_with_rehashed_result(self):
        self.step()
        event = self.path / "events/0001"
        accepted = event / "capture/0001.accepted.json"
        value = run.journal.read(accepted); value["result"]["criterion_assessments"][0]["status"] = "missed"
        accepted.write_bytes(run.guard._json_bytes(value))
        result = run.journal.read(event / "result.json")
        result["capture_hashes"] = run.rehearsal.file_hashes(event / "capture")
        (event / "result.json").write_bytes(run.guard._json_bytes(result))
        with self.assertRaisesRegex(ValueError, "interpretation"): self.replay()

    def test_linked_or_orphan_events_rejected(self):
        self.step()
        (self.path / "events/0003").mkdir()
        with self.assertRaises(ValueError): self.replay()
        (self.path / "events/0003").rmdir()
        (self.path / "events/0001/extra").symlink_to(self.path / "manifest.json")
        with self.assertRaises(ValueError): self.replay()


if __name__ == "__main__":
    unittest.main()
