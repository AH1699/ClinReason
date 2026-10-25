"""Offline diagnostic tests: fake credentials, certificates and HTTP only."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import grok_trace_s43 as trace
from tests.test_transport_s39 import Connection, Response, candidate
from tests.test_usage_s39 import usage_fixture
from tests.test_workflow_s38 import envelope, judgment_fixture

ROOT = Path(__file__).resolve().parents[1]
KEY = "S43-NOT-A-REAL-SECRET"


class Socket:
    def getpeercert(self, binary_form=False):
        return b"fake certificate" if binary_form else {"subject": [[("commonName", "api.x.ai")]],
            "issuer": [[("commonName", "Fake test CA")]], "subjectAltName": [("DNS", "api.x.ai")]}
    def version(self): return "TLSv1.3"
    def getpeername(self): return ("192.0.2.1", 443)


class FakeConnection(Connection):
    def connect(self): self.sock = Socket()


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.expires = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        self.protocol = trace.audit(ROOT)

    def execute(self, bodies):
        self.connections = []
        def factory(host, timeout):
            self.assertEqual(host, "api.x.ai")
            response = bodies[len(self.connections)]
            c = FakeConnection(response); self.connections.append(c); return c
        with redirect_stdout(StringIO()):
            return trace.execute(ROOT, self.directory, self.protocol, KEY,
                connection_factory=factory, expires_at=self.expires, mode="offline_fixture")

    def test_original_payload_is_exact_not_reworded(self):
        data = trace.packets(ROOT)
        self.assertEqual(len(data), 2)
        self.assertEqual(trace.hashlib.sha256(trace.live.guard._json_bytes(data[1][1])).hexdigest(), trace.ORIGINAL_HASH)
        self.assertNotIn("schema", json.dumps(data[0][1]))

    def test_allowlist_does_not_keep_auth_cookie_or_location(self):
        response = Response(headers={"x-request-id": "request-1", "Set-Cookie": KEY,
            "Authorization": KEY, "Location": "https://other.example/", "server": "test"})
        self.assertEqual(trace.safe_headers(response, KEY)["allowlisted_response_headers"],
                         {"x-request-id": "request-1", "server": "test"})

    def test_allowlisted_value_cannot_echo_key(self):
        result = trace.safe_headers(Response(headers={"x-request-id": "prefix-"+KEY}), KEY)
        self.assertEqual(result["allowlisted_response_headers"], {})
        self.assertEqual(result["omitted_allowlisted_fields"], ["x-request-id"])

    def test_oversized_control_character_and_nonascii_headers_omitted(self):
        for value in ("x"*257, "line\r\ninjection", "非ASCII", 4):
            self.assertEqual(trace.safe_headers(Response(headers={"server": value}), KEY)["allowlisted_response_headers"], {})

    def test_full_diagnostic_keeps_original_payload_and_metadata(self):
        packet = trace.packets(ROOT)[1][2]
        raw = json.loads(envelope({"model": "grok-4.7", "provider": "grok"}, json.dumps(judgment_fixture(packet))))
        raw["usage"] = usage_fixture("grok")
        report = self.execute([Response(candidate(), headers={"x-request-id": "one", "cf-ray": "fake-edge-1"}),
                               Response(json.dumps(raw).encode(), headers={"x-request-id": "two"})])
        self.assertEqual(report["terminal"], "diagnostic_complete")
        self.assertEqual(report["attempts_reserved"], 2)
        self.assertFalse(report["benchmark_resumed"])
        self.assertEqual(report["scores_added_to_benchmark"], 0)
        self.assertTrue(all(c.closed for c in self.connections))
        self.assertEqual(trace.hashlib.sha256((self.directory/"capture/0002.payload.json").read_bytes()).hexdigest(), trace.ORIGINAL_HASH)
        for path in (self.directory/"trace").iterdir():
            self.assertNotIn(KEY, path.read_text())
        self.assertIn("x-request-id", (self.directory/"trace/0002.response-headers.json").read_text())

    def test_403_headers_and_raw_body_saved_without_retry(self):
        body = b'{"code":"permission-denied","error":"synthetic rejection"}'
        report = self.execute([Response(body, status=403, headers={"cf-ray": "test-edge"})])
        self.assertEqual(report["terminal"], "unknown_charge")
        self.assertEqual(len(self.connections), 1)
        self.assertEqual((self.directory/"capture/0001.raw.bin").read_bytes(), body)
        self.assertEqual(trace.live.load_json(self.directory/"trace/0001.response-headers.json")["status"], 403)
        self.assertEqual(report["capture_accounting"]["unknown_charge_attempts"], 1)

    def test_threshold_crossing_retains_reply_and_prevents_second_call(self):
        raw = json.loads(candidate()); raw["usage"]["cost_in_usd_ticks"] = trace.THRESHOLD+1
        report = self.execute([Response(json.dumps(raw).encode())])
        self.assertEqual(report["terminal"], "spend_threshold_reached")
        self.assertTrue(report["results"][0]["accepted"])
        self.assertEqual(len(self.connections), 1)
        self.assertGreater(Decimal(report["reported_known_total_usd"]), 1)

    def test_missing_usage_stops_before_second_request(self):
        raw = json.loads(candidate()); del raw["usage"]
        report = self.execute([Response(json.dumps(raw).encode())])
        self.assertEqual(report["terminal"], "unknown_charge")
        self.assertEqual(len(self.connections), 1)

    def test_expired_receipt_does_not_dispatch(self):
        self.expires = "2020-01-01T00:00:00Z"
        report = self.execute([])
        self.assertEqual(report["terminal"], "approval_expired")
        self.assertEqual(len(self.connections), 0)

    def test_no_output_directory_reuse(self):
        self.execute([Response(b"error", status=403)])
        with self.assertRaises(FileExistsError): self.execute([])

    def test_response_closed_if_metadata_cannot_be_saved(self):
        response = Response(b"body")
        observed = trace.ObservedConnection(FakeConnection(response), self.directory, 1, "api.x.ai", KEY)
        with patch.object(observed, "record", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): observed.getresponse()
        self.assertTrue(response.closed)

    def test_wrong_host_or_path_rejected_before_connection(self):
        connection = FakeConnection(Response())
        for host, path in (("other.example", "/v1/responses"), ("api.x.ai", "/changed")):
            observed = trace.ObservedConnection(connection, self.directory, 1, host, KEY)
            with self.assertRaises(ValueError): observed.request("POST", path, b"{}", {})
        self.assertEqual(connection.calls, [])

    def test_missing_authorization_never_loads_key_or_connects(self):
        with patch.object(trace.live, "read_setting", side_effect=AssertionError) as key:
            with patch.object(trace.live, "create_tls_connection", side_effect=AssertionError) as network:
                with self.assertRaises((ValueError, OSError)):
                    trace.run(ROOT, self.directory/"missing.json")
        key.assert_not_called(); network.assert_not_called()

    def test_snapshot_matches_without_network(self):
        self.assertEqual(trace.snapshot(ROOT), trace.live.load_json(ROOT/trace.FREEZE))


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.current = datetime.now(timezone.utc)
        patch.object(trace, "audit", return_value="OFFLINE-FIXTURE-ONLY").start()
        self.ignored = patch.object(trace.live.subprocess, "run", return_value=SimpleNamespace(returncode=0)).start()
        self.key = patch.object(trace.live, "read_setting", side_effect=AssertionError("No credentials in tests")).start()
        self.network = patch.object(trace.live, "create_tls_connection", side_effect=AssertionError("No network in tests")).start()
        self.addCleanup(patch.stopall)
        self.receipt = {"version": trace.VERSION, "protocol_sha256": "OFFLINE-FIXTURE-ONLY",
            "maximum_attempts": 2, "stop_threshold_usd": "1.00", "hard_ceiling": False,
            "overshoot_accepted": True, "paid_calls_approved": True, "data_export_approved": True,
            "benchmark_restart_approved": False, "approval_id": str(uuid4()), "run_id": str(uuid4()),
            "issued_at": (self.current-timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "expires_at": (self.current+timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "authorization_text": "OFFLINE FIXTURE ONLY", "authorization_evidence": "Unit test, not human consent"}
        directory = trace.live._private_path(self.root, "work/s43-authorizations", directory=True, create=True)
        self.path = directory/(self.receipt["approval_id"]+".json")
        trace.live.guard._write_exclusive(self.path, trace.live.guard._json_bytes(self.receipt))

    def blocked(self):
        with self.assertRaises((ValueError, OSError)): trace.run(self.root, self.path)
        self.key.assert_not_called(); self.network.assert_not_called()

    def test_receipt_validation_is_read_only(self):
        self.assertEqual(trace.validate_receipt(self.root, self.path), self.receipt)
        self.key.assert_not_called(); self.network.assert_not_called()

    def test_changed_scope_and_types_rejected_before_credentials(self):
        for key, value in {"protocol_sha256": "wrong", "maximum_attempts": True, "stop_threshold_usd": "55.00",
                "paid_calls_approved": 1, "data_export_approved": False, "overshoot_accepted": False,
                "hard_ceiling": True, "benchmark_restart_approved": True, "authorization_text": "",
                "authorization_evidence": "", "extra_field": True}.items():
            with self.subTest(key=key), patch.object(trace.capture, "strict_json", return_value={**self.receipt, key: value}):
                self.blocked()

    def test_expired_future_and_long_lived_receipts_rejected(self):
        for issued, expires in ((-2, -1), (1, 2), (-1, 25)):
            receipt = {**self.receipt,
                "issued_at": (self.current+timedelta(hours=issued)).isoformat().replace("+00:00", "Z"),
                "expires_at": (self.current+timedelta(hours=expires)).isoformat().replace("+00:00", "Z")}
            with patch.object(trace.capture, "strict_json", return_value=receipt): self.blocked()

    def test_reused_receipt_rejected(self):
        directory = trace.live._private_path(self.root, "work/s43-authorizations/consumed", directory=True, create=True)
        trace.live.guard._write_exclusive(directory/self.path.name, b"{}")
        self.blocked()
        with patch.object(trace.capture, "strict_json", return_value={**self.receipt, "run_id": str(uuid4())}):
            self.blocked()

    def test_existing_output_rejected(self):
        trace.live._private_path(self.root, "work/s43-runs/"+self.receipt["run_id"], directory=True, create=True)
        self.blocked()

    def test_public_receipt_permissions_rejected(self):
        self.path.chmod(0o644); self.blocked()

    def test_unignored_output_rejected(self):
        self.ignored.return_value.returncode = 1; self.blocked()

    def test_key_failure_consumes_approval_and_saves_no_secret(self):
        with self.assertRaises(AssertionError): trace.run(self.root, self.path)
        self.network.assert_not_called()
        report = trace.live.load_json(self.root/"work/s43-runs"/self.receipt["run_id"]/"report.json")
        self.assertEqual(report["terminal"], "credential_load_failure")
        self.assertEqual(report["attempts_reserved"], 0)
        self.key.reset_mock(); self.blocked()


if __name__ == "__main__":
    unittest.main()
