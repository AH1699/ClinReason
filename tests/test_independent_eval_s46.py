"""No-network regression for the conservative tier adapter and seven-row prefix."""

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import independent_eval_s46 as run
from tests.test_independent_eval_s45 import connection, finish, KEYS
from tests.test_transport_s39 import Response

ROOT = Path(__file__).resolve().parents[1]
SPEC = {"provider": "minimax", "model": "MiniMax-M3", "input_per_million": .3, "output_per_million": 1.2}
PAYLOAD = {"model": "MiniMax-M3", "service_tier": "standard"}


def raw():
    return {"model": "MiniMax-M3", "service_tier": "default", "usage": {
        "prompt_tokens": 402, "completion_tokens": 7306, "total_tokens": 7708,
        "completion_tokens_details": {"reasoning_tokens": 6819}, "prompt_tokens_details": {"cached_tokens": 128}}}


def default_tier(row, reply, response):
    if row["model"] == "MiniMax-M3":
        reply["service_tier"] = "default"
        return Response(json.dumps(reply).encode())
    return response


def fixture_prefix(directory):
    s = run.old.Session(ROOT, directory, run.old.plan(ROOT), "FIXTURE", mode="offline_fixture")
    finish(s, default_tier)
    row = s.rows[6]
    cap = directory / "jobs" / run.old.job_id(row) / "capture"
    reply = run.read_json(cap / "0001.raw.bin")
    result = run.workflow.decode_candidate(reply, "minimax", "MiniMax-M3")
    family = s.catalog[row["family_id"]][0]
    binding = {"case_version": family["version"], "case_content_hash": run.workflow.variant_hash(family, row["language"]),
        "answer_sha256": run.sha256_json(result), "raw_sha256": run.read_json(cap / "0001.capture.json")["body_sha256"],
        "payload_sha256": run.read_json(cap / "0001.attempt.json")["payload_sha256"]}
    estimated = run.account(reply, SPEC, PAYLOAD)
    accounts = s.accounts[:6] + [estimated]
    return {"source_sha256": "FIXTURE-PREFIX", "attempts": 7, "answers": s.bank()["answers"] + [{"row": row, "result": result, "binding": binding}],
        "accounts": accounts, "monitoring_ticks": sum(run.old.monitoring_delta(a, r["provider"])["delta_ticks"] for a, r in zip(accounts, s.rows)),
        "new_tier_estimate": estimated, "historical_s45_unknown_unchanged": True}


class TierTests(unittest.TestCase):
    def test_conservative_math_and_original_data_preserved(self):
        value = raw(); before = deepcopy(value)
        result = run.account(value, SPEC, PAYLOAD)
        self.assertEqual(result["undiscounted_token_estimate_microusd"], 13332)
        self.assertEqual(value, before)
        self.assertEqual(value["service_tier"], "default")
        self.assertFalse(result["invoice_or_tier_verified"])
        self.assertEqual(result["usage"]["output_tokens_for_estimate"], 7306)

    def test_no_generic_unknown_cost_override(self):
        for payload in (None, {"model": "MiniMax-M3"}, {**PAYLOAD, "service_tier": "priority"}, {**PAYLOAD, "model": "other"}):
            self.assertEqual(run.account(raw(), SPEC, payload)["status"], "unknown")
        for tier in ("unknown", "priority"):
            self.assertEqual(run.account({**raw(), "service_tier": tier}, SPEC, PAYLOAD)["status"], "unknown")
        self.assertEqual(run.account({**raw(), "model": "alias"}, SPEC, PAYLOAD)["status"], "unknown")

    def test_invalid_and_long_usage_remains_unknown(self):
        value = raw(); value["usage"]["total_tokens"] += 1
        self.assertEqual(run.account(value, SPEC, PAYLOAD)["status"], "unknown")
        value = raw(); value["usage"]["prompt_tokens"] = 17000; value["usage"]["total_tokens"] = 24306
        self.assertEqual(run.account(value, SPEC, PAYLOAD)["status"], "unknown")


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.prefix = fixture_prefix(Path(cls.temp.name)/"source")
        cls.complete = run.Session(ROOT, Path(cls.temp.name)/"complete", cls.prefix, "FIXTURE", "offline_fixture")
        finish(cls.complete, default_tier)
        cls.complete.seal_bank()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory(); self.addCleanup(self.temp_case.cleanup)

    def new(self):
        return run.Session(ROOT, Path(self.temp_case.name)/"new", self.prefix, "FIXTURE", "offline_fixture")

    def test_first_job_eight_reuses_seventh_answer_no_regeneration(self):
        s = self.new()
        self.assertEqual(len(s.rows), 61)
        self.assertEqual(s.rows[0]["sequence"], 8)
        self.assertEqual(len(s.answers), 7)
        self.assertEqual(s.report()["attempts"], 7)
        self.assertEqual(s.monitored, self.prefix["monitoring_ticks"])
        finish(s, default_tier, stop_at=1)
        row = s.rows[0]
        self.assertEqual(row["model"], "MiniMax-M3")
        self.assertEqual(row["stage"], "update")
        self.assertIn(s.answers[run.workflow.answer_key(row, "initial")]["text"], json.dumps(s.contexts[8]["payload"]))

    def test_full_fixture_total68_all16answers_and8scores(self):
        report = self.complete.report()
        self.assertEqual(report["new_attempts"], 61)
        self.assertEqual(report["attempts"], 68)
        self.assertEqual(report["accepted_answer_stages"], 16)
        self.assertEqual(report["accounting"]["attempts"], 68)
        self.assertEqual(len(report["score_records"]), 8)
        self.assertTrue(report["complete"])
        self.assertTrue(report["historical_s45_unknown_unchanged"])

    def test_replay_matches_and_no_network_allowed(self):
        s = run.replay(ROOT, self.complete.directory, self.prefix, "FIXTURE")
        self.assertEqual(s.report(), self.complete.report())
        with self.assertRaises(run.guard.AdmissionBlocked):
            s.step(KEYS, lambda *a, **k: self.fail())

    def test_unknown_new_charge_stops_with_prefix_preserved(self):
        s = self.new()
        finish(s, lambda row, reply, response: Response(b"Denied", 403))
        report = s.report()
        self.assertEqual(report["attempts"], 8)
        self.assertEqual(report["new_attempts"], 1)
        self.assertEqual(report["accepted_answer_stages"], 7)
        self.assertEqual(report["accounting"]["unknown_charge_attempts"], 1)
        self.assertEqual(s.terminal, "unknown_charge")
        self.assertIsNone(s.step(KEYS, lambda *a, **k: self.fail()))

    def test_capture_write_interruption_recovers_without_network(self):
        s = self.new(); original = run.write_json
        def fail(path, value):
            if Path(path).name == "result.json": raise OSError("fixture")
            return original(path, value)
        with patch.object(run, "write_json", side_effect=fail):
            with self.assertRaises(OSError): s.step(KEYS, connection(s, default_tier))
        before = s.report()
        recovered = run.replay(ROOT, s.directory, self.prefix, "FIXTURE")
        self.assertEqual(recovered.report()["accepted_answer_stages"], 8)
        self.assertEqual(recovered.report()["attempts"], 8)
        self.assertEqual(recovered.report()["monitoring_amount_usd"], before["monitoring_amount_usd"])

    def test_shared_threshold_accounts_for_carried_spending(self):
        s = self.new()
        s.spec["stop_threshold_usd"] = format(Decimal(self.prefix["monitoring_ticks"] + 1) / run.old.TICKS_PER_USD, "f")
        finish(s, default_tier)
        self.assertEqual(s.terminal, "spend_threshold_reached")
        self.assertEqual(s.report()["attempts"], 8)

    def test_source_or_protocol_tampering_rejected(self):
        prefix = deepcopy(self.prefix); prefix["source_sha256"] = "other"
        with self.assertRaises(ValueError): run.replay(ROOT, self.complete.directory, prefix, "FIXTURE")
        with self.assertRaises(ValueError): run.replay(ROOT, self.complete.directory, self.prefix, "other")

    def test_source_slot_uses_exclusive_write(self):
        path = Path(self.temp_case.name)/"slot.json"
        run.write_json(path, {"source_sha256": "one"})
        with self.assertRaises(FileExistsError): run.write_json(path, {"source_sha256": "one"})


if __name__ == "__main__":
    unittest.main()
