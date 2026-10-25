"""Offline only; no real credentials or network."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import grok_output_cap_s44 as cap
from tests.test_grok_trace_s43 import FakeConnection
from tests.test_transport_s39 import Response
from tests.test_usage_s39 import usage_fixture
from tests.test_workflow_s38 import envelope, judgment_fixture

ROOT = Path(__file__).resolve().parents[1]


class CapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.expiry = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        self.connections = []

    def execute(self, response):
        def factory(host, timeout):
            self.assertEqual(host, "api.x.ai")
            self.assertFalse(self.connections, "More than one call")
            connection = FakeConnection(response); self.connections.append(connection)
            return connection
        return cap.execute(ROOT, self.directory, cap.audit(ROOT), "OFFLINE-FAKE-KEY",
            expires_at=self.expiry, connection_factory=factory, mode="offline_fixture")

    def test_only_cap_removed(self):
        original = cap.trace.packets(ROOT)[1][1]
        modified, _ = cap.packet(ROOT)
        self.assertNotIn("max_output_tokens", modified)
        self.assertNotIn("max_tokens", modified)
        self.assertEqual({**modified, "max_output_tokens": 8192}, original)
        self.assertEqual(cap.snapshot(ROOT), cap.live.load_json(ROOT/cap.FREEZE))

    def test_403_saved_once_and_cost_unknown(self):
        body = b'{"code":"permission-denied","error":"synthetic rejection"}'
        report = self.execute(Response(body, status=403, headers={"x-request-id": "test-only"}))
        self.assertEqual(report["attempts_reserved"], 1)
        self.assertEqual(report["terminal"], "unknown_charge")
        self.assertEqual(report["capture_accounting"]["unknown_charge_attempts"], 1)
        self.assertFalse(report["benchmark_resumed"])
        self.assertEqual(report["scores_added_to_benchmark"], 0)
        self.assertEqual((self.directory/"capture/0001.raw.bin").read_bytes(), body)
        self.assertTrue(self.connections[0].closed)

    def valid_response(self, charge=1234):
        packet = cap.packet(ROOT)[1]
        raw = json.loads(envelope({"provider": "grok", "model": "grok-4.7"}, json.dumps(judgment_fixture(packet))))
        raw["usage"] = usage_fixture("grok"); raw["usage"]["cost_in_usd_ticks"] = charge
        return Response(json.dumps(raw).encode())

    def test_success_still_exactly_one_call_no_benchmark_score(self):
        report = self.execute(self.valid_response())
        self.assertTrue(report["accepted"])
        self.assertEqual(report["terminal"], "diagnostic_complete")
        self.assertEqual(report["attempts_reserved"], 1)
        self.assertEqual(report["scores_added_to_benchmark"], 0)

    def test_threshold_overrun_retained_and_no_second_call(self):
        report = self.execute(self.valid_response(cap.trace.THRESHOLD+1))
        self.assertEqual(report["terminal"], "spend_threshold_reached")
        self.assertEqual(report["attempts_reserved"], 1)

    def test_expired_approval_no_dispatch(self):
        self.expiry = "2020-01-01T00:00:00Z"
        with self.assertRaises(ValueError): self.execute(Response())
        self.assertEqual(self.connections, [])

    def test_existing_output_cannot_resume(self):
        self.execute(Response(b"error", status=403))
        with self.assertRaises(FileExistsError): self.execute(Response())

    def test_missing_receipt_does_not_read_key(self):
        with patch.object(cap.live, "read_setting", side_effect=AssertionError) as key:
            with self.assertRaises((ValueError, OSError)): cap.run(ROOT, self.directory/"missing.json")
        key.assert_not_called()


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.now = datetime.now(timezone.utc)
        patch.object(cap, "audit", return_value="OFFLINE-FIXTURE").start()
        self.ignored = patch.object(cap.live.subprocess, "run", return_value=SimpleNamespace(returncode=0)).start()
        self.key = patch.object(cap.live, "read_setting", side_effect=AssertionError("No real key")).start()
        self.network = patch.object(cap.live, "create_tls_connection", side_effect=AssertionError("No network")).start()
        self.addCleanup(patch.stopall)
        self.receipt = {"version": cap.VERSION, "protocol_sha256": "OFFLINE-FIXTURE", "maximum_attempts": 1,
            "only_change": "omit_max_output_tokens", "stop_threshold_usd": "1.00", "hard_ceiling": False,
            "overshoot_accepted": True, "paid_calls_approved": True, "data_export_approved": True,
            "benchmark_restart_approved": False, "owner_reports_account_limit_set": False,
            "approval_id": str(uuid4()), "run_id": str(uuid4()), "authorization_text": "OFFLINE FIXTURE",
            "authorization_evidence": "Unit test, not human approval",
            "issued_at": (self.now-timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "expires_at": (self.now+timedelta(hours=1)).isoformat().replace("+00:00", "Z")}
        directory = cap.live._private_path(self.root, "work/s44-authorizations", directory=True, create=True)
        self.path = directory/(self.receipt["approval_id"]+".json")
        cap.guard._write_exclusive(self.path, cap.guard._json_bytes(self.receipt))

    def blocked(self):
        with self.assertRaises((ValueError, OSError)): cap.run(self.root, self.path)
        self.key.assert_not_called(); self.network.assert_not_called()

    def test_validation_read_only(self):
        self.assertEqual(cap.validate(self.root, self.path), self.receipt)
        self.key.assert_not_called(); self.network.assert_not_called()

    def test_scope_type_and_extra_fields_rejected(self):
        for field, value in {"maximum_attempts": 2, "paid_calls_approved": 1, "hard_ceiling": True,
                "data_export_approved": False, "benchmark_restart_approved": True,
                "only_change": "different_prompt", "owner_reports_account_limit_set": True,
                "protocol_sha256": "wrong", "extra": True}.items():
            with patch.object(cap.capture, "strict_json", return_value={**self.receipt, field: value}): self.blocked()

    def test_invalid_dates_rejected(self):
        for issued, expires in ((-2,-1),(1,2),(-1,25)):
            value = {**self.receipt, "issued_at": (self.now+timedelta(hours=issued)).isoformat().replace("+00:00", "Z"),
                "expires_at": (self.now+timedelta(hours=expires)).isoformat().replace("+00:00", "Z")}
            with patch.object(cap.capture, "strict_json", return_value=value): self.blocked()

    def test_key_failure_consumes_once(self):
        with self.assertRaises(AssertionError): cap.run(self.root, self.path)
        self.network.assert_not_called(); self.key.reset_mock(); self.blocked()
        report = cap.live.load_json(self.root/"work/s44-runs"/self.receipt["run_id"]/"report.json")
        self.assertEqual(report["attempts_reserved"], 0)
        self.assertEqual(report["terminal"], "credential_load_failure")

    def test_private_permissions_required(self):
        self.path.chmod(0o644); self.blocked()

    def test_git_ignore_required(self):
        self.ignored.return_value.returncode = 1; self.blocked()


if __name__ == "__main__":
    unittest.main()
