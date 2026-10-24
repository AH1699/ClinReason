"""Offline only: fake credentials/connections and temporary authorization roots."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import ssl
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from benchmark import live_s41 as live
from benchmark.config import load_json
from tests.test_transport_s39 import Connection, Response
from tests.test_usage_s39 import usage_fixture
from tests.test_workflow_s38 import reply_fixture

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEYS = {p: "S41-FAKE-NOT-A-CREDENTIAL" for p in live.KEY_NAMES}


def fake_connection(session):
    def factory(host, timeout):
        row = session.pending
        raw = json.loads(reply_fixture(session))
        raw["usage"] = usage_fixture(row["provider"])
        return Connection(Response(json.dumps(raw).encode()))
    return factory


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.now = datetime.now(timezone.utc)
        self.audit = patch.object(live, "audit", return_value={"protocol_sha256": "FIXTURE-NOT-VALID-LIVE"}).start()
        self.addCleanup(patch.stopall)
        self.ignored = patch.object(live.subprocess, "run", return_value=SimpleNamespace(returncode=0)).start()
        self.keys = patch.object(live, "load_credentials", side_effect=AssertionError("Real keys forbidden in tests")).start()
        self.network = patch.object(live, "create_tls_connection", side_effect=AssertionError("Network forbidden in tests")).start()
        self.receipt = {"version": live.VERSION, "approval_id": str(uuid4()), "run_id": str(uuid4()),
            "protocol_sha256": "FIXTURE-NOT-VALID-LIVE", "phase": "first", "maximum_attempts": 816,
            "stop_threshold_usd": "55.00", "hard_ceiling": False, "overshoot_accepted": True,
            "data_export_approved": True, "paid_calls_approved": True, "confirmation_authorized": False,
            "issued_at": (self.now-timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "expires_at": (self.now+timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "authorization_text": "OFFLINE FIXTURE ONLY, not actual human authorization",
            "authorization_evidence": "Unit test fixture"}
        self.receipt["output_directory"] = "work/s41-runs/"+self.receipt["run_id"]
        directory = live._private_path(self.root, "work/s41-authorizations", directory=True, create=True)
        self.path = directory/(self.receipt["approval_id"]+".json")

    def write(self, receipt=None):
        live.guard._write_exclusive(self.path, live.guard._json_bytes(receipt or self.receipt))

    def assert_blocked(self):
        with self.assertRaises((ValueError, OSError)):
            live.run_live(self.root, self.path)
        self.keys.assert_not_called(); self.network.assert_not_called()

    def test_missing_receipt_before_credentials(self):
        self.assert_blocked()

    def test_exact_receipt_only_validates_does_not_authorize_network(self):
        self.write()
        self.assertEqual(live.validate_approval(self.root, self.path, self.now), self.receipt)
        self.keys.assert_not_called(); self.network.assert_not_called()

    def test_changed_scope_false_flags_booleans_and_extra_fields_rejected(self):
        variants = {"protocol_sha256": "wrong", "phase": "confirmation", "maximum_attempts": True,
                    "stop_threshold_usd": "90.00", "data_export_approved": False, "paid_calls_approved": 1,
                    "overshoot_accepted": False, "hard_ceiling": True, "confirmation_authorized": True,
                    "output_directory": "work/other", "authorization_text": "", "authorization_evidence": ""}
        for key, value in variants.items():
            with self.subTest(key=key), patch.object(live.capture, "strict_json", return_value={**self.receipt, key: value}):
                if not self.path.exists(): self.write()
                self.assert_blocked()
        with patch.object(live.capture, "strict_json", return_value={**self.receipt, "approved": True}):
            self.assert_blocked()

    def test_expired_future_and_long_lived_receipts(self):
        self.write()
        for issued, expires in ((-2, -1), (1, 2), (-1, 25)):
            record = {**self.receipt,
                "issued_at": (self.now+timedelta(hours=issued)).isoformat().replace("+00:00", "Z"),
                "expires_at": (self.now+timedelta(hours=expires)).isoformat().replace("+00:00", "Z")}
            with patch.object(live.capture, "strict_json", return_value=record): self.assert_blocked()

    def test_reused_receipt_cannot_reset_with_new_run_id(self):
        self.write(); live.consume_approval(self.root, self.receipt)
        self.assert_blocked()
        run_id = str(uuid4())
        with patch.object(live.capture, "strict_json", return_value={**self.receipt, "run_id": run_id,
                "output_directory": "work/s41-runs/"+run_id}): self.assert_blocked()

    def test_cross_process_style_consumption_is_exclusive(self):
        self.write()
        # Pre-create the directory; competing O_EXCL writes share one nonce.
        live._private_path(self.root, "work/s41-authorizations/consumed", directory=True, create=True)
        def attempt(_):
            try:
                live.consume_approval(self.root, self.receipt); return True
            except FileExistsError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt, range(2))), [False, True])

    def test_existing_output_forbids_resume(self):
        self.write(); live._private_path(self.root, self.receipt["output_directory"], directory=True, create=True)
        self.assert_blocked()

    def test_symlink_receipt_rejected(self):
        other = self.root/"other.json"
        live.guard._write_exclusive(other, live.guard._json_bytes(self.receipt))
        self.path.symlink_to(other); self.assert_blocked()

    def test_public_permissions_rejected(self):
        self.write(); self.path.chmod(0o644); self.assert_blocked()

    def test_git_nonignored_paths_rejected(self):
        self.write(); self.ignored.return_value.returncode = 1; self.assert_blocked()

    def test_duplicate_json_rejected(self):
        live.guard._write_exclusive(self.path, b'{"version":1,"version":2}')
        self.assert_blocked()

    def test_credential_failure_consumes_receipt_and_saves_safe_report(self):
        self.write()
        original = live.Session
        with patch.object(live, "Session", side_effect=lambda root, directory, protocol, mode:
                          original(ROOT, directory, protocol, mode=mode)):
            with self.assertRaises(live.guard.AdmissionBlocked): live.run_live(self.root, self.path)
        self.network.assert_not_called()
        report = load_json(self.root/self.receipt["output_directory"]/"report.json")
        self.assertEqual(report["attempts_reserved"], 0)
        self.assertEqual(report["terminal"], "local_failure_or_interruption")
        with self.assertRaises(live.guard.AdmissionBlocked):
            live.validate_approval(self.root, self.path)

    def test_live_entry_calls_only_fake_connector_and_stops_on_failure(self):
        self.write(); self.keys.side_effect = None; self.keys.return_value = dict(FAKE_KEYS)
        original = live.Session
        self.network.side_effect = lambda *a, **k: Connection(Response(b"error", status=503))
        with patch.object(live, "Session", side_effect=lambda root, directory, protocol, mode:
                          original(ROOT, directory, protocol, mode=mode)), redirect_stdout(StringIO()):
            report = live.run_live(self.root, self.path)
        self.network.assert_called_once()
        self.assertFalse(report["complete"])
        self.assertEqual(report["mode"], "live")  # Exercises production labeling with fake HTTP only.
        self.assertNotIn('"live_calls": 0', json.dumps(report))
        self.assertEqual(report["spending"]["unknown_settled_charges"], 1)

    def test_protocol_drift_after_consumption_blocks_first_dispatch(self):
        self.write(); self.keys.side_effect = None; self.keys.return_value = dict(FAKE_KEYS)
        self.audit.side_effect = [{"protocol_sha256": "FIXTURE-NOT-VALID-LIVE"}, live.guard.AdmissionBlocked("drift")]
        original = live.Session
        with patch.object(live, "Session", side_effect=lambda root, directory, protocol, mode:
                          original(ROOT, directory, protocol, mode=mode)):
            with self.assertRaises(live.guard.AdmissionBlocked): live.run_live(self.root, self.path)
        self.network.assert_not_called()
        report = load_json(self.root/self.receipt["output_directory"]/"report.json")
        self.assertEqual(report["attempts_reserved"], 0)

    def test_expiry_after_admission_stops_without_network(self):
        self.write(); self.keys.side_effect = None; self.keys.return_value = dict(FAKE_KEYS)
        original = live.Session
        # Validation uses real time; credential loading moves the dispatch clock forward.
        def keys(root):
            clock = patch.object(live, "datetime").start()
            clock.now.return_value = self.now+timedelta(hours=2)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            return dict(FAKE_KEYS)
        self.keys.side_effect = keys
        with patch.object(live, "Session", side_effect=lambda root, directory, protocol, mode:
                          original(ROOT, directory, protocol, mode=mode)):
            report = live.run_live(self.root, self.path)
        self.network.assert_not_called()
        self.assertEqual(report["terminal"], "approval_expired")


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.session = live.Session(ROOT, Path(self.temp.name)/"run", "fixture-only", mode="offline_fixture")

    def step(self):
        return self.session.step(FAKE_KEYS, connection_factory=fake_connection(self.session))

    def test_complete_816_step_run_with_real_orchestrator_and_fake_http(self):
        while self.session.terminal is None: self.assertTrue(self.step()["accepted"])
        report = self.session.report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["attempts_reserved"], 816)
        self.assertTrue(report["control_gate"]["pass"])
        self.assertTrue(report["stability_diagnostics"]["pass"])
        self.assertEqual(len(report["score_records"]), 264)
        self.assertTrue(all(r["simulation_only"] for r in report["score_records"]))
        self.assertEqual(len(report["separate_judge_reports"]), 2)
        for path in self.session.directory.rglob("*.json"):
            self.assertNotIn(FAKE_KEYS["gemini"], path.read_text())

    def test_known_threshold_overrun_keeps_answer_and_stops(self):
        self.session.monitor.monitored = 55*spending_ticks()-1
        self.assertTrue(self.step()["accepted"])
        self.assertEqual(len(self.session.judgments), 1)
        self.assertEqual(self.session.terminal, "spend_threshold_reached")
        self.assertIsNone(self.step())

    def test_bad_control_gate_prevents_candidate_call(self):
        for _ in range(72): self.step()
        self.session.judgments.clear()
        with patch.object(live.workflow, "request_context", side_effect=AssertionError("Must not build candidate")):
            self.assertIsNone(self.step())
        self.assertEqual(self.session.terminal, "control_gate_failed")
        self.assertEqual(self.session.capture.index, 72)

    def test_unknown_cost_and_truncated_raw_retained_no_retry(self):
        result = self.session.step(FAKE_KEYS, connection_factory=lambda *a, **k:
            Connection(Response(chunks=[b"prefix", TimeoutError("S41-secret")])) )
        self.assertFalse(result["accepted"])
        self.assertEqual((self.session.capture.directory/"0001.raw.bin").read_bytes(), b"prefix")
        self.assertEqual(self.session.monitor.report()["unknown_settled_charges"], 1)
        self.assertIsNone(self.step())

    def test_interrupt_settles_unknown_and_stops(self):
        with self.assertRaises(KeyboardInterrupt):
            self.session.step(FAKE_KEYS, connection_factory=lambda *a, **k:
                Connection(Response(chunks=[b"prefix", KeyboardInterrupt()])))
        self.assertEqual(self.session.monitor.unknown, 1)
        self.assertIsNone(self.step())

    def test_no_artificial_fixture_cost_journal_in_new_runner(self):
        self.step()
        self.assertFalse((self.session.directory/"workflow").exists())
        self.assertEqual(self.session.monitor.estimated, self.session.capture.accounts[0]["undiscounted_token_estimate_microusd"])

    def test_progress_disk_failure_keeps_charge_and_prevents_new_call(self):
        original = live.guard._write_exclusive
        def write(path, body):
            if path.name.endswith(".progress.json"):
                raise OSError("simulated disk failure")
            original(path, body)
        with patch.object(live.guard, "_write_exclusive", side_effect=write):
            with self.assertRaises(OSError): self.step()
        self.assertGreater(self.session.monitor.estimated, 0)
        self.assertEqual(len(self.session.judgments), 1)
        self.assertIsNone(self.step())

    def test_missing_cells_keep_full_denominator_no_fake_eighty(self):
        report = self.session.report()
        for value in report["separate_judge_reports"].values():
            self.assertIsNone(value["point_mean"])


def spending_ticks():
    return live.spending_s40.TICKS_PER_USD


class ProtocolTests(unittest.TestCase):
    def test_tls_uses_verifying_default_context_and_fixed_hosts(self):
        with patch.object(live, "HTTPSConnection") as connection:
            live.create_tls_connection("api.x.ai", timeout=900)
            context = connection.call_args.kwargs["context"]
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            with self.assertRaises(live.guard.AdmissionBlocked):
                live.create_tls_connection("unapproved.example", timeout=900)
            connection.assert_called_once()

    def test_plan_and_audit_never_read_credentials_or_open_connection(self):
        with patch.object(live, "load_credentials", side_effect=AssertionError), patch.object(live, "create_tls_connection", side_effect=AssertionError):
            report, proposal = live.audit(ROOT), live.proposal(ROOT)
        self.assertFalse(report["live_authorized"])
        self.assertFalse(proposal["paid_calls_approved"])
        self.assertFalse(proposal["data_export_approved"])
        self.assertEqual(proposal["maximum_attempts"], 816)

    def test_snapshot_drift_blocks_before_keys(self):
        with patch.object(live, "snapshot", return_value={}):
            with self.assertRaises(live.guard.AdmissionBlocked): live.audit(ROOT)

    def test_checked_in_snapshot_and_proposal_match(self):
        self.assertEqual(live.snapshot(ROOT), load_json(ROOT/live.FREEZE))
        self.assertEqual(live.proposal(ROOT), load_json(ROOT/live.PROPOSAL))


if __name__ == "__main__":
    unittest.main()
