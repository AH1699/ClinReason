"""No-network S47 scope, failure, replay and numerical regression tests."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import judge_observation_s47 as run
from tests.test_transport_s39 import Connection, Response
from tests.test_workflow_s38 import judgment_fixture, envelope
from tests.test_usage_s39 import usage_fixture

ROOT = Path(__file__).resolve().parents[1]


def source_fixture():
    selected = run.jobs(ROOT); initial = {}
    for lang in ("en", "zh-Hans"):
        job = next(j for j in selected if j["row"]["language"] == lang)
        packet = run.score.stage_packet(job["context"]["full"], "initial", job["context"]["packet"]["level_definitions"])
        initial[lang] = {"row": {"language": lang}, "judgment": judgment_fixture(packet), "packet_sha256": run.sha256_json(packet)}
    return {"source_sha256": "FIXTURE-SOURCE", "source_protocol_sha256": "FIXTURE-S46",
            "initial_sha256": run.sha256_json(initial), "initial": initial}


def factory(change=None):
    selected = run.jobs(ROOT); state = {"calls": 0}
    def connect(host, timeout):
        i = state["calls"]; state["calls"] += 1
        job = selected[i]
        judgment = judgment_fixture(job["context"]["packet"], job["row"]["profile"])
        raw = json.loads(envelope(job["row"], json.dumps(judgment)))
        raw["usage"] = usage_fixture("gemini")
        response = Response(json.dumps(raw).encode())
        return Connection(change(i+1, raw, judgment, response) if change else response)
    return connect, state


class ScopeTests(unittest.TestCase):
    def test_eight_updates_only_and_exact_repeats(self):
        selected = run.jobs(ROOT)
        self.assertEqual(len(selected), 8)
        self.assertTrue(all(j["row"]["kind"] == "judge" and j["row"]["block"] == "control"
                            and j["row"]["stage"] == "update" and j["row"]["model"] == run.MODEL for j in selected))
        self.assertEqual(selected[0]["context"], selected[6]["context"])
        self.assertEqual(selected[1]["context"], selected[7]["context"])
        self.assertEqual([j["row"]["profile"] for j in selected], ["safe"]*2+["partial"]*2+["unsafe"]*2+["safe"]*2)

    def test_payload_only_changes_instruction_and_descriptions(self):
        for job in run.jobs(ROOT):
            original = job["original_payload"]; new = deepcopy(job["context"]["payload"])
            self.assertEqual(new["system_instruction"], original["system_instruction"]+"\n"+run.draft.CHECKLIST)
            new["system_instruction"] = original["system_instruction"]
            fields = new["response_format"]["schema"]["properties"]["dimension_observations"]["items"]["properties"]
            for name in ("overlap_note", "new_fact", "independent_consequence_or_failure", "response_evidence"):
                fields[name].pop("description")
            self.assertEqual(new, original)
            self.assertNotIn('"profile"', original["input"])
            self.assertNotIn('"expected_unsafe_error_id"', original["input"])

    def test_changed_initial_or_source_hash_blocks(self):
        value = source_fixture(); plan = {k:value[k] for k in ("source_sha256", "source_protocol_sha256", "initial_sha256")}
        run.verify_source(value, plan)
        value["initial"]["en"]["judgment"]["criterion_assessments"][0]["status"] = "partial"
        with self.assertRaises(ValueError): run.verify_source(value, plan)
        value = source_fixture(); value["initial"]["en"]["packet_sha256"] = "other"
        with self.assertRaises(ValueError): run.validate_initials(run.jobs(ROOT), value)

    def test_consumed_protocol_blocks_fresh_uuid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run.consume(root, "fixture-protocol", "first")
            with self.assertRaises(FileExistsError): run.consume(root, "fixture-protocol", "different")


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name); self.value = source_fixture()

    def execute(self, change=None, **kwargs):
        connection, state = factory(change)
        report = run.execute(ROOT, self.path, self.value, "FIXTURE", "S47-FAKE-KEY", connection, "offline_fixture", **kwargs)
        self.assertEqual(report["attempts"], state["calls"])
        return report

    def replay(self):
        return run.replay(ROOT, self.path, self.value, "FIXTURE")

    def test_complete_fixture_gate_and_no_candidate_score(self):
        report = self.execute()
        self.assertEqual(report["attempts"], 8)
        self.assertTrue(report["gate"]["pass"])
        self.assertEqual(report["candidate_calls"], 0)
        self.assertEqual(report["candidate_scores"], 0)
        self.assertEqual([r["score"]["point_score"] for r in report["control_records"]], [100,100,65,65,20,20,100,100])
        self.assertEqual(report, self.replay())
        text = json.dumps(report)
        self.assertNotIn("S47-FAKE-KEY", text)
        self.assertNotIn("response_evidence", text)

    def test_blank_observations_stop_without_repair(self):
        def change(i, raw, judgment, response):
            for row in judgment["dimension_observations"]:
                row["overlap_note"] = ""; row["new_fact"] = ""
            raw["steps"][0]["content"][0]["text"] = json.dumps(judgment)
            return Response(json.dumps(raw).encode())
        report = self.execute(change)
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(report["terminal"], "response_validation")
        self.assertEqual(len(report["failures"][0]["missing_observation_fields"]), 3)
        self.assertEqual(report["accepted_update_judgments"], 0)
        self.assertEqual(report, self.replay())

    def test_http_failure_stops_unknown_charge(self):
        report = self.execute(lambda *a: Response(b"Denied",403))
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(report["accounting"]["unknown_charge_attempts"], 1)
        self.assertEqual(report["terminal"], "unknown_charge")

    def test_threshold_stops_after_last_request_overrun(self):
        report = self.execute(threshold=1)
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(report["terminal"], "spend_threshold_reached")
        self.assertGreater(float(report["monitoring_amount_usd"]), 0)

    def test_same_directory_cannot_repeat_execution(self):
        self.execute()
        with self.assertRaises(FileExistsError): self.execute()

    def test_raw_tampering_detected(self):
        self.execute()
        path = self.path/"capture"/"0001.raw.bin"
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaises(ValueError): self.replay()

    def test_accounting_tampering_detected(self):
        self.execute()
        path = self.path/"capture"/"0001.accounting.json"
        value = run.read_json(path); value["undiscounted_token_estimate_microusd"] += 1
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.replay()

    def test_bad_quote_remains_rejected(self):
        def change(i, raw, judgment, response):
            judgment["criterion_assessments"][0]["response_evidence"] = "Fabricated span absent from the answer"
            raw["steps"][0]["content"][0]["text"] = json.dumps(judgment)
            return Response(json.dumps(raw).encode())
        self.assertEqual(self.execute(change)["terminal"], "response_validation")

    def test_capture_before_report_failure_is_readable_without_network(self):
        original = run.write_json
        def fail(path, value):
            if path.name == "report.json": raise OSError("fixture")
            original(path, value)
        with patch.object(run, "write_json", side_effect=fail):
            with self.assertRaises(OSError): self.execute()
        self.assertEqual(self.replay()["attempts"], 8)
        self.assertTrue(self.replay()["gate"]["pass"])

    def test_reserved_attempt_without_payload_retains_unknown(self):
        original = run.guard._write_exclusive
        def fail(path, value):
            if path.name.endswith(".payload.json"): raise OSError("fixture")
            original(path, value)
        with patch.object(run.guard, "_write_exclusive", side_effect=fail):
            with self.assertRaises(OSError): self.execute()
        report = self.replay()
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(report["accounting"]["unknown_charge_attempts"], 1)
        self.assertEqual(report["terminal"], "interrupted_unknown_delivery_or_charge")


if __name__ == "__main__":
    unittest.main()
