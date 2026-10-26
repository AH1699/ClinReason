"""Offline fixtures only: no real credentials, approval or provider request."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import mixed_live_s54 as run
from tests.test_mixed_panel_s51 import ROOT, imports, reply


class AdmissionTests(unittest.TestCase):
    def ready(self):
        spec = run.journal.read(ROOT / run.PLAN)
        self.now = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        spec.update(status="ready_for_explicit_approval", stop_threshold_usd="1.00",
            pricing_verification={"verified_at": "2026-10-25T11:00:00Z", "verified_by": "TEST ONLY",
                "sources": run.PRICING_URLS, "rates": run.rates(ROOT), "evidence_note": "Fixture, not verification"})
        freeze = {"test_only": True}
        approval = {"approval_id": str(uuid4()), "run_id": str(uuid4()),
            "protocol_sha256": run.panel.sha256_json(freeze), "approved_at": "2026-10-25T11:30:00Z",
            "expires_at": "2026-10-25T13:00:00Z", "approved_by": "TEST ONLY",
            "authorization_evidence": "Fixture, not human approval", "accept_provider_disclosure": True,
            "accept_reporting_policy": True, "accept_threshold_overrun": True, "accept_paid_calls": True}
        return spec, freeze, approval

    def check(self, spec, freeze, approval):
        with patch.object(run.journal, "read", return_value=spec), patch.object(run, "snapshot", return_value={"test_only": True}):
            return run.validate_authorization(ROOT, freeze, approval, self.now)

    def test_proposal_without_approval_blocks_before_keys_or_network(self):
        with patch.object(run.panel.old.prior, "read_setting") as key, patch.object(run.panel.old.prior, "create_tls_connection") as network:
            with self.assertRaises(ValueError): run.run_live(ROOT, {}, {}, str(uuid4()))
            key.assert_not_called(); network.assert_not_called()

    def test_exact_fresh_policy_can_be_admitted_in_mock(self):
        spec, freeze, approval = self.ready()
        self.assertEqual(self.check(spec, freeze, approval)["plan"]["maximum_attempts"], 452)

    def test_each_positive_permission_required(self):
        spec, freeze, approval = self.ready()
        for name in ("accept_provider_disclosure", "accept_reporting_policy", "accept_threshold_overrun", "accept_paid_calls"):
            for wrong in (False, 1, "yes", None):
                changed = deepcopy(approval); changed[name] = wrong
                with self.subTest(name=name, wrong=wrong), self.assertRaises(ValueError): self.check(spec, freeze, changed)

    def test_expired_future_and_overlong_approval_blocked(self):
        spec, freeze, approval = self.ready()
        for field, value in (("expires_at", "2026-10-25T12:00:00Z"), ("approved_at", "2026-10-25T12:01:00Z"),
                             ("expires_at", "2026-10-27T12:00:00Z"), ("approved_at", "2026-10-25T11:00:00")):
            changed = deepcopy(approval); changed[field] = value
            with self.assertRaises(ValueError): self.check(spec, freeze, changed)

    def test_price_evidence_old_future_wrong_rates_or_missing_is_blocked(self):
        spec, freeze, approval = self.ready()
        for field, value in (("verified_at", "2026-10-23T11:00:00Z"), ("verified_at", "2026-10-26T11:00:00Z"),
                             ("rates", {}), ("sources", {}), ("evidence_note", "")):
            changed = deepcopy(spec); changed["pricing_verification"][field] = value
            with self.assertRaises(ValueError): self.check(changed, freeze, approval)

    def test_scope_budget_freeze_and_protocol_changes_blocked(self):
        spec, freeze, approval = self.ready()
        for field, value in (("maximum_attempts", 453), ("maximum_attempts", True), ("automatic_retries", 1),
                             ("resume_allowed", True), ("hard_ceiling", True), ("stop_threshold_usd", "NaN"),
                             ("stop_threshold_usd", "0.00"), ("stop_threshold_usd", "1.001")):
            changed = deepcopy(spec); changed[field] = value
            with self.assertRaises(ValueError): self.check(changed, freeze, approval)
        with self.assertRaises(ValueError): self.check(spec, {"changed": True}, approval)
        approval["protocol_sha256"] = "0" * 64
        with self.assertRaises(ValueError): self.check(spec, freeze, approval)

    def test_consumption_cannot_be_reused_with_new_run_or_same_run(self):
        _, _, approval = self.ready()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            with self.assertRaises(ValueError): run.consume_approval(directory, approval, "x", str(uuid4()))
            run.consume_approval(directory, approval, approval["protocol_sha256"], approval["run_id"])
            with self.assertRaises(FileExistsError): run.consume_approval(directory, approval, approval["protocol_sha256"], approval["run_id"])
            self.assertEqual(len(list(directory.iterdir())), 1)

    def test_live_entry_consumes_approval_before_credentials_and_does_not_retry_failures(self):
        spec, freeze, approval = self.ready()
        checked = {"protocol_sha256": approval["protocol_sha256"], "plan": spec}
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp).resolve() / "runs"; parent.mkdir()
            consumed = Path(temp).resolve() / "consumed"; consumed.mkdir()
            def key(*args, **kwargs):
                self.assertTrue((consumed / (approval["approval_id"] + ".json")).exists())
                raise ValueError("TEST secret must not escape")
            with patch.object(run, "validate_authorization", return_value=checked), \
                 patch.object(run.panel, "verified_source", return_value={"bank": {"answers": imports()}}), \
                 patch.object(run.panel.old.prior, "_private_path", side_effect=[parent, consumed]), \
                 patch.object(run.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
                 patch.object(run.panel.old.prior, "read_setting", side_effect=key), \
                 patch.object(run.panel.old.prior, "create_tls_connection") as network:
                with self.assertRaises(run.guard.AdmissionBlocked) as caught:
                    run.run_live(ROOT, freeze, approval, approval["run_id"])
                self.assertNotIn("secret", str(caught.exception))
                network.assert_not_called()
            with self.assertRaises(FileExistsError):
                run.consume_approval(consumed, approval, approval["protocol_sha256"], approval["run_id"])

    def test_source_failure_does_not_consume_or_read_keys(self):
        spec, freeze, approval = self.ready()
        with patch.object(run, "validate_authorization", return_value={"protocol_sha256": "test", "plan": spec}), \
             patch.object(run.panel, "verified_source", side_effect=ValueError("bad source")), \
             patch.object(run, "consume_approval") as consume, patch.object(run.panel.old.prior, "read_setting") as key:
            with self.assertRaises(ValueError): run.run_live(ROOT, freeze, approval, approval["run_id"])
            consume.assert_not_called(); key.assert_not_called()


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.records = imports()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / "run"
        self.writer = run.Session(ROOT, self.path, self.records, "fixture-protocol", "1.00", mode="offline_fixture")
        self.connections = []

    def step(self, transform=None, status=200, fault=None):
        def factory(host, *, timeout):
            event = self.path / "events" / f"{self.writer.event:04d}"
            self.assertTrue((event / "reservation.json").exists())
            self.assertTrue((event / "capture/0001.attempt.json").exists())
            connection = run.rehearsal._Connection(run.rehearsal.Fixture(reply(self.writer.core, transform), status, {}, fault))
            self.connections.append(connection)
            return connection
        return self.writer.step({"gemini": "FIXTURE", "minimax": "FIXTURE"}, factory)

    def replay(self): return run.replay(ROOT, self.path, "fixture-protocol")

    def test_full_452_schedule_and_readonly_replay(self):
        while self.step() is not None: pass
        before = {str(p): p.read_bytes() for p in self.path.rglob("*") if p.is_file()}
        value = self.replay()
        self.assertEqual(value["transport_attempts"], 452)
        self.assertEqual(value["answer_stages_present"], 144)
        self.assertEqual(len(value["conversations"]), 72)
        self.assertEqual(value["live_calls"], 0)
        self.assertFalse(value["interrupted"])
        self.assertTrue(value["control_gate"]["pass"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.path.rglob("*") if p.is_file()})

    def test_http_error_valid_body_stops_and_never_counts_answer(self):
        self.step(status=403)
        value = self.replay()
        self.assertEqual((value["answer_stages_present"], value["unknown_charge_attempts"]), (16, 1))
        self.assertIsNone(self.step())
        self.assertEqual(len(self.connections), 1)

    def test_timeout_and_interrupt_do_not_retry(self):
        self.step(fault="read_timeout")
        self.assertEqual(self.replay()["unknown_charge_attempts"], 1)
        self.assertIsNone(self.step())

    def test_interrupt_preserves_prefix_and_poisoned_writer(self):
        with self.assertRaises(KeyboardInterrupt): self.step(fault="interrupt")
        with self.assertRaises(ValueError): self.step()
        value = self.replay()
        self.assertTrue(value["interrupted"])
        self.assertEqual(value["unknown_charge_attempts"], 1)

    def test_no_capture_yet_is_reservation_not_a_billed_attempt(self):
        with patch.object(run.capture, "CaptureJournal", side_effect=OSError("disk")), self.assertRaises(OSError): self.step()
        value = self.replay()
        self.assertEqual((value["transport_attempts"], value["unknown_charge_attempts"]), (0,0))
        self.assertTrue(value["unresolved_request_reservation"])

    def test_orphan_and_linked_paths_rejected(self):
        self.step()
        extra = self.path / "events/0003"; extra.mkdir()
        with self.assertRaises(ValueError): self.replay()
        extra.rmdir()
        (self.path / "events/0001/extra").symlink_to(self.path / "manifest.json")
        with self.assertRaises(ValueError): self.replay()

    def test_known_cost_invalid_response_closes_lane_not_panel(self):
        self.step(lambda raw: raw.update(status="incomplete"))
        self.step()
        self.assertEqual(self.replay()["transport_attempts"], 2)
        self.assertEqual(self.replay()["outcomes"]["skipped"], 1)

    def test_unknown_usage_stops_globally(self):
        self.step(lambda raw: raw.pop("usage"))
        self.assertEqual(self.replay()["unknown_charge_attempts"], 1)
        self.assertIsNone(self.step())

    def test_threshold_overrun_stops_after_last_request(self):
        self.path = Path(self.temp.name).resolve() / "threshold-run"
        self.writer = run.Session(ROOT, self.path, self.records, "fixture-protocol", "0.01", mode="offline_fixture")
        def expensive(raw):
            raw["usage"] = {"total_input_tokens": 10000, "total_output_tokens": 10000,
                            "total_thought_tokens": 1000, "total_tokens": 21000}
        self.step(expensive)
        self.assertEqual(self.writer.core.terminal, "spend_threshold_reached")
        self.assertEqual(self.replay()["terminal"], "spend_threshold_reached")
        self.assertIsNone(self.step())

    def test_result_write_failure_preserves_known_accounting_on_readonly_inspection(self):
        original = run.journal.write
        def broken(path, value):
            if path.name == "result.json": raise OSError("fixture disk failure")
            return original(path, value)
        with patch.object(run.journal, "write", side_effect=broken), self.assertRaises(OSError): self.step()
        with self.assertRaises(ValueError): self.step()
        value = self.replay()
        self.assertTrue(value["interrupted"])
        self.assertEqual((value["transport_attempts"], value["answer_stages_present"], value["unknown_charge_attempts"]), (1, 17, 0))

    def test_tamper_rejected_and_no_reopen(self):
        self.step()
        with self.assertRaises(FileExistsError): run.Session(ROOT, self.path, self.records, "fixture-protocol", "1.00", mode="offline_fixture")
        (self.path / "events/0001/capture/0001.raw.bin").write_bytes(b"{}")
        with self.assertRaises(ValueError): self.replay()

    def test_no_fixture_metadata_is_persisted_in_live_session_manifest(self):
        path = Path(self.temp.name).resolve() / "live-shaped-test"
        writer = run.Session(ROOT, path, self.records, "fixture-protocol", "1.00", mode="live")
        self.assertEqual(run.journal.read(path / "manifest.json")["mode"], "live")
        # No step is performed; live provenance must reject these fixture imports.
        with self.assertRaises(ValueError), patch.object(run.panel, "verified_source", return_value={"bank": {"answers": []}}):
            run.replay(ROOT, path, "fixture-protocol")


if __name__ == "__main__": unittest.main()
