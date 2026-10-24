"""Offline audit regression tests; fake keys and injected replies only."""
import json
from pathlib import Path
import tempfile
import unittest

from benchmark import live_s41 as live
from scripts.audit_s41_control_stop import audit
from tests.test_live_s41 import FAKE_KEYS, fake_connection
from tests.test_transport_s39 import Connection, Response

ROOT = Path(__file__).resolve().parents[1]


class SavedControlStopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)/"run"
        session = live.Session(ROOT, self.directory, live.audit(ROOT)["protocol_sha256"], mode="live")
        # "live" exercises labeling; no network or real keys are used.
        session.step(FAKE_KEYS, connection_factory=fake_connection(session))
        session.step(FAKE_KEYS, connection_factory=lambda *a, **k: Connection(Response(
            b'{"code":"permission-denied","error":"Synthetic test rejection"}', status=403)))
        live.guard._write_exclusive(self.directory/"report.json", live.guard._json_bytes(session.report()))

    def change(self, path, key, value):
        target = self.directory/path
        data = json.loads(target.read_bytes()); data[key] = value
        target.write_bytes(live.guard._json_bytes(data))

    def test_replays_exact_prefix_and_unknown_final_charge(self):
        result = audit(ROOT, self.directory)
        self.assertTrue(result["offline_replay_pass"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["accepted_control_judgments"], 1)
        self.assertEqual(result["unknown_charge_attempts"], 1)
        self.assertEqual(result["candidate_scores"], 0)
        self.assertFalse(result["calibration_complete"])

    def test_changed_payload_rejected(self):
        self.change("capture/0001.payload.json", "model", "changed")
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_changed_model_identity_rejected(self):
        self.change("capture/0001.attempt.json", "model", "changed")
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_changed_accounting_rejected(self):
        self.change("capture/0001.accounting.json", "undiscounted_token_estimate_microusd", 0)
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_changed_raw_bytes_rejected(self):
        (self.directory/"capture/0001.raw.bin").write_bytes(b"changed")
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_extra_dispatch_after_stop_rejected(self):
        live.guard._write_exclusive(self.directory/"capture/0003.attempt.json", b"{}")
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_missing_attempt_rejected(self):
        (self.directory/"capture/0001.attempt.json").unlink()
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_changed_ledger_rejected(self):
        self.change("spending/0002.settlement.json", "monitoring_after_ticks", 0)
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_spurious_score_rejected(self):
        self.change("report.json", "score_records", [{"point_score": 80}])
        with self.assertRaises(ValueError): audit(ROOT, self.directory)

    def test_fixture_cannot_be_presented_as_live_capture(self):
        self.change("capture/0001.capture.json", "fixture_only", True)
        with self.assertRaises(ValueError): audit(ROOT, self.directory)


if __name__ == "__main__":
    unittest.main()
