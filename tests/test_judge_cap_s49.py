"""Offline mechanical checks; no provider calls or clinical score expectations."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import judge_cap_s49 as run
from tests.test_judge_saved_bank_s48 import source_fixture as bank_fixture
from tests.test_transport_s39 import Connection, Response
from tests.test_workflow_s38 import judgment_fixture, envelope
from tests.test_usage_s39 import usage_fixture

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    jobs = run.prior.jobs(ROOT, bank_fixture(), "offline_fixture")
    bundle = {"job": jobs[51], "initial_packet": jobs[50]["context"]["packet"],
              "initial": judgment_fixture(jobs[50]["context"]["packet"])}
    return {"mode": "offline_fixture", "source_sha256": "FIXTURE-SOURCE", "source_protocol_sha256": "FIXTURE-S48",
            "bundle_sha256": run.sha256_json(bundle), "bundle": bundle}


class ScopeTests(unittest.TestCase):
    def test_only_cap_changes(self):
        value = fixture(); before = deepcopy(value)
        outgoing = run.request(value)
        self.assertEqual(outgoing["generation_config"]["max_output_tokens"], 32768)
        outgoing["generation_config"]["max_output_tokens"] = 8192
        self.assertEqual(outgoing, value["bundle"]["job"]["context"]["payload"])
        self.assertEqual(value, before)

    def test_source_cell_and_bundle_are_bound(self):
        for mutation in ("candidate", "stage", "hash", "cap", "initial"):
            value = fixture(); bundle = value["bundle"]
            if mutation == "candidate": bundle["job"]["row"]["candidate_model"] = "OTHER"
            if mutation == "stage": bundle["job"]["row"]["stage"] = "initial"
            if mutation == "cap": bundle["job"]["context"]["payload"]["generation_config"]["max_output_tokens"] = 1000
            if mutation == "initial": bundle["initial_packet"]["transcript"][-1]["content"] += "changed"
            value["bundle_sha256"] = "wrong" if mutation == "hash" else run.sha256_json(bundle)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): run.request(value)

    def test_fixture_cannot_be_live(self):
        value = fixture()
        with self.assertRaises(ValueError): run.verify(ROOT, value, "live")
        value["mode"] = "live"
        with self.assertRaises(ValueError): run.verify(ROOT, value, "live")

    def test_one_use_allowance(self):
        with tempfile.TemporaryDirectory() as temp:
            run.consume(Path(temp), "fixture-protocol", "one")
            with self.assertRaises(FileExistsError): run.consume(Path(temp), "fixture-protocol", "two")


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name); self.value = fixture(); self.calls = 0

    def execute(self, change=None, **kwargs):
        def connect(host, timeout):
            self.calls += 1
            job = self.value["bundle"]["job"]
            result = judgment_fixture(job["context"]["packet"])
            raw = json.loads(envelope(job["row"], json.dumps(result)))
            raw["usage"] = usage_fixture("gemini")
            response = change(raw, result) if change else Response(json.dumps(raw).encode())
            return Connection(response)
        return run.execute(ROOT, self.path, self.value, "FIXTURE", "S49-FAKE-KEY", connect, "offline_fixture", **kwargs)

    def replay(self, **kwargs):
        return run.replay(ROOT, self.path, self.value, "FIXTURE", **kwargs)

    def test_success_is_separate_and_reproducible(self):
        result = self.execute()
        self.assertEqual(self.calls, 1)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["terminal"], "supplement_complete")
        self.assertTrue(result["accepted"])
        self.assertIsNotNone(result["supplemental_score"])
        self.assertFalse(result["s48_complete"])
        self.assertFalse(result["scores_pooled"])
        self.assertEqual(result["candidate_calls"], 0)
        self.assertEqual(result, self.replay())
        self.assertNotIn("S49-FAKE-KEY", json.dumps(result))
        self.assertNotIn("response_evidence", json.dumps(result))

    def test_http_error_no_retry_unknown_not_zero(self):
        result = self.execute(lambda *a: Response(b"Forbidden", 403))
        self.assertEqual(self.calls, 1)
        self.assertEqual(result["terminal"], "unknown_charge")
        self.assertIsNone(result["monitoring_amount_usd"])
        self.assertIsNone(result["supplemental_score"])

    def test_missing_usage_blocks_acceptance(self):
        def change(raw, result):
            raw.pop("usage")
            return Response(json.dumps(raw).encode())
        result = self.execute(change)
        self.assertEqual(result["terminal"], "unknown_charge")
        self.assertFalse(result["accepted"])

    def test_incomplete_response_still_accounts_cost(self):
        def change(raw, result):
            raw["status"] = "incomplete"
            return Response(json.dumps(raw).encode())
        result = self.execute(change)
        self.assertEqual(result["terminal"], "response_validation")
        self.assertGreater(float(result["monitoring_amount_usd"]), 0)
        self.assertFalse(result["accepted"])

    def test_invalid_quote_rejected(self):
        def change(raw, result):
            result["criterion_assessments"][0]["response_evidence"] = "NOT PRESENT"
            raw["steps"][0]["content"][0]["text"] = json.dumps(result)
            return Response(json.dumps(raw).encode())
        self.assertEqual(self.execute(change)["terminal"], "response_validation")

    def test_wrong_model_rejected(self):
        def change(raw, result):
            raw["model"] = "OTHER"
            return Response(json.dumps(raw).encode())
        self.assertEqual(self.execute(change)["category"], "model_identity")

    def test_threshold_is_not_a_hard_cap(self):
        result = self.execute(threshold=1)
        self.assertEqual(result["terminal"], "spend_threshold_reached")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["hard_ceiling"])
        self.assertEqual(result, self.replay(threshold=1))

    def test_no_resume(self):
        self.execute()
        with self.assertRaises(FileExistsError): self.execute()
        self.assertEqual(self.calls, 1)

    def test_tampered_raw_account_or_acceptance_rejected(self):
        self.execute()
        for name in ("raw.bin", "accounting.json", "accepted.json"):
            path = self.path / "capture" / ("0001." + name); original = path.read_bytes()
            if name == "raw.bin": path.write_bytes(original + b" ")
            else:
                value = json.loads(original)
                if name == "accounting.json": value["undiscounted_token_estimate_microusd"] += 1
                else: value["raw_sha256"] = "changed"
                path.write_text(json.dumps(value))
            with self.subTest(name=name), self.assertRaises(ValueError): self.replay()
            path.write_bytes(original)

    def test_extra_attempt_rejected(self):
        self.execute()
        (self.path / "capture" / "0002.attempt.json").write_text("{}")
        with self.assertRaises(ValueError): self.replay()

    def test_reserved_without_payload_stays_unknown(self):
        original = run.guard._write_exclusive
        def fail(path, value):
            if path.name.endswith(".payload.json"): raise OSError("fixture")
            original(path, value)
        with patch.object(run.guard, "_write_exclusive", side_effect=fail):
            with self.assertRaises(OSError): self.execute()
        result = self.replay()
        self.assertEqual(result["terminal"], "interrupted_unknown_delivery_or_charge")
        self.assertEqual(result["attempts"], 1)
        self.assertIsNone(result["monitoring_amount_usd"])
        self.assertEqual(self.calls, 0)

    def test_report_failure_retains_replay(self):
        original = run.write_json
        def fail(path, value):
            if path.name == "report.json": raise OSError("fixture")
            original(path, value)
        with patch.object(run, "write_json", side_effect=fail):
            with self.assertRaises(OSError): self.execute()
        self.assertTrue(self.replay()["accepted"])
        self.assertEqual(self.calls, 1)


if __name__ == "__main__":
    unittest.main()
