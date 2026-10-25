"""Offline-only saved-bank, gate, persistence and spending regression checks."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import judge_saved_bank_s48 as run
from tests.test_transport_s39 import Connection, Response
from tests.test_workflow_s38 import judgment_fixture, envelope
from tests.test_usage_s39 import usage_fixture

ROOT = Path(__file__).resolve().parents[1]


def source_fixture():
    spec = run.plan(ROOT); catalog = run.workflow.families(ROOT)
    answers = []
    for row in run.workflow.schedule(ROOT):
        if row["kind"] != "candidate" or row["family_id"] not in spec["families"] or row["model"] not in spec["candidate_models"]:
            continue
        family = catalog[row["family_id"]][0]
        result = {"text": f'Saved fixture {row["stage"]} answer. Not clinical advice.'}
        answers.append({"row": row, "result": result, "binding": {
            "case_version": family["version"], "case_content_hash": run.workflow.variant_hash(family, row["language"]),
            "answer_sha256": run.sha256_json(result), "raw_sha256": "FIXTURE", "payload_sha256": "FIXTURE"}})
    bank = {"mode": "offline_fixture", "candidate_models": spec["candidate_models"],
            "families": spec["families"], "answers": answers}
    return {"mode": "offline_fixture", "source_sha256": "FIXTURE-SOURCE", "source_protocol_sha256": "FIXTURE-S46",
            "bank_sha256": run.sha256_json(bank), "bank": bank}


def factory(value, change=None):
    selected = run.jobs(ROOT, value, "offline_fixture"); state = {"calls": 0}
    def connect(host, timeout):
        i = state["calls"]; state["calls"] += 1
        job = selected[i]
        judgment = judgment_fixture(job["context"]["packet"], job["row"]["profile"])
        raw = json.loads(envelope(job["row"], json.dumps(judgment)))
        raw["usage"] = usage_fixture("gemini")
        response = Response(json.dumps(raw).encode())
        return Connection(change(job, raw, judgment, response) if change else response)
    return connect, state


class ScopeTests(unittest.TestCase):
    def test_exact_schedule_only_judges_and_identical_repeat_packets(self):
        selected = run.jobs(ROOT, source_fixture(), "offline_fixture")
        self.assertEqual(len(selected), 52)
        self.assertTrue(all(j["row"]["kind"] == "judge" and j["row"]["model"] == run.MODEL for j in selected))
        self.assertTrue(all(j["row"]["block"] == "control" for j in selected[:36]))
        self.assertTrue(all(j["row"]["block"] == "development" for j in selected[36:]))
        originals = {run.workflow.judgment_key(j["row"]): j for j in selected if not j["row"]["repeat"]}
        repeats = [j for j in selected if j["row"]["repeat"]]
        self.assertEqual(len(repeats), 12)
        for job in repeats:
            first = originals[run.workflow.judgment_key({**job["row"], "repeat": False})]
            self.assertEqual(first["context"], job["context"])

    def test_initial_instruction_unchanged_and_no_control_profile_leak(self):
        for job in run.jobs(ROOT, source_fixture(), "offline_fixture"):
            packet, payload = job["context"]["packet"], job["context"]["payload"]
            expected = run.score.instruction(ROOT, packet)
            if packet["scoring_stage"] == "update":
                expected += "\n" + run.draft.CHECKLIST
            self.assertEqual(payload["system_instruction"], expected)
            self.assertNotIn('"profile"', payload["input"])
            self.assertNotIn('"candidate_model"', payload["input"])
            self.assertNotIn('"expected_unsafe_error_id"', payload["input"])
            self.assertEqual(payload["generation_config"]["max_output_tokens"], 8192)

    def test_missing_duplicate_changed_or_wrong_family_answer_rejected(self):
        for mutation in ("missing", "duplicate", "changed", "family"):
            value = source_fixture(); answers = value["bank"]["answers"]
            if mutation == "missing": answers.pop()
            elif mutation == "duplicate": answers.append(deepcopy(answers[0]))
            elif mutation == "changed": answers[0]["result"]["text"] += " altered"
            else: value["bank"]["families"] = ["OTHER"]
            value["bank_sha256"] = run.sha256_json(value["bank"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                run.jobs(ROOT, value, "offline_fixture")

    def test_live_source_requires_pinned_hashes_and_mode(self):
        value = source_fixture()
        with self.assertRaises(ValueError): run.verify_source(value, run.plan(ROOT), "live")
        value["mode"] = value["bank"]["mode"] = "live"
        value["bank_sha256"] = run.sha256_json(value["bank"])
        with self.assertRaises(ValueError): run.verify_source(value, run.plan(ROOT), "live")

    def test_consumed_protocol_cannot_get_new_allowance(self):
        with tempfile.TemporaryDirectory() as temp:
            run.consume(Path(temp), "fixture-protocol", "one")
            with self.assertRaises(FileExistsError): run.consume(Path(temp), "fixture-protocol", "two")


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name); self.value = source_fixture()

    def execute(self, change=None, **kwargs):
        connection, state = factory(self.value, change)
        result = run.execute(ROOT, self.path, self.value, "FIXTURE", "S48-FAKE-KEY", connection, "offline_fixture", **kwargs)
        self.assertEqual(result["attempts"], state["calls"])
        return result

    def replay(self, **kwargs):
        return run.replay(ROOT, self.path, self.value, "FIXTURE", **kwargs)

    def test_complete_fixture_scores_eight_saved_conversations(self):
        result = self.execute()
        self.assertEqual(result["attempts"], 52)
        self.assertEqual(result["candidate_calls"], 0)
        self.assertEqual(result["saved_answer_stages"], 16)
        self.assertEqual(len(result["candidate_score_records"]), 8)
        self.assertTrue(result["gate"]["pass"])
        self.assertEqual(result["gate"]["repeat_stage_vectors"], 12)
        self.assertTrue(result["complete"])
        self.assertTrue(all(r["simulation_only"] for r in result["candidate_score_records"]))
        self.assertFalse(result["model_rankings_approved"])
        self.assertEqual(result, self.replay())
        self.assertNotIn("S48-FAKE-KEY", json.dumps(result))
        self.assertNotIn("response_evidence", json.dumps(result))

    def test_failed_control_gate_blocks_all_candidate_scoring(self):
        def change(job, raw, judgment, response):
            if job["row"]["profile"] == "unsafe":
                judgment["critical_errors"] = []
                raw["steps"][0]["content"][0]["text"] = json.dumps(judgment)
                return Response(json.dumps(raw).encode())
            return response
        result = self.execute(change)
        self.assertEqual(result["attempts"], 36)
        self.assertEqual(result["terminal"], "control_gate_failed")
        self.assertEqual(result["candidate_score_records"], [])
        self.assertEqual(result["candidate_summary"]["expected_cells"], 8)
        self.assertIsNone(result["candidate_summary"]["point_mean"])
        self.assertEqual(result, self.replay())

    def test_blank_required_field_stops_without_repair(self):
        def change(job, raw, judgment, response):
            if job["row"]["stage"] == "update":
                judgment["dimension_observations"][0]["overlap_note"] = ""
                raw["steps"][0]["content"][0]["text"] = json.dumps(judgment)
                return Response(json.dumps(raw).encode())
            return response
        result = self.execute(change)
        self.assertEqual(result["terminal"], "response_validation")
        self.assertEqual(result["accepted_judgments"], result["attempts"] - 1)
        self.assertEqual(result["candidate_score_records"], [])
        self.assertEqual(result["failures"][0]["missing_observation_fields"], ["dimension_observations[0].overlap_note"])

    def test_invalid_quote_remains_rejected(self):
        def change(job, raw, judgment, response):
            judgment["criterion_assessments"][0]["response_evidence"] = "NOT IN THIS ANSWER"
            raw["steps"][0]["content"][0]["text"] = json.dumps(judgment)
            return Response(json.dumps(raw).encode())
        self.assertEqual(self.execute(change)["terminal"], "response_validation")

    def test_http_failure_keeps_unknown_cost_and_never_retries(self):
        result = self.execute(lambda *a: Response(b"Forbidden", 403))
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["accounting"]["unknown_charge_attempts"], 1)
        self.assertEqual(result["terminal"], "unknown_charge")

    def test_success_response_with_missing_usage_stops(self):
        def change(job, raw, judgment, response):
            raw.pop("usage")
            return Response(json.dumps(raw).encode())
        result = self.execute(change)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["terminal"], "unknown_charge")

    def test_threshold_stops_after_last_request_overrun(self):
        result = self.execute(threshold=1)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["terminal"], "spend_threshold_reached")
        self.assertGreater(float(result["monitoring_amount_usd"]), 0)
        self.assertEqual(result, self.replay(threshold=1))

    def test_failure_during_candidates_keeps_completed_scores_and_missing_cells(self):
        def change(job, raw, judgment, response):
            return Response(b"Denied", 403) if job["row"]["sequence"] == 39 else response
        result = self.execute(change)
        self.assertEqual(result["attempts"], 39)
        self.assertTrue(result["gate"]["pass"])
        self.assertGreater(len(result["candidate_score_records"]), 0)
        self.assertLess(len(result["candidate_score_records"]), 8)
        self.assertIsNone(result["candidate_summary"]["point_mean"])
        self.assertEqual(result["candidate_summary"]["expected_cells"], 8)

    def test_same_directory_cannot_resume(self):
        self.execute(threshold=1)
        with self.assertRaises(FileExistsError): self.execute()

    def test_replay_rejects_dispatch_after_spending_stop(self):
        self.execute()
        with self.assertRaisesRegex(ValueError, "Dispatch after stop"):
            self.replay(threshold=1)

    def test_wrong_returned_model_stops_without_score(self):
        def change(job, raw, judgment, response):
            raw["model"] = "different-model"
            return Response(json.dumps(raw).encode())
        result = self.execute(change)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["failures"][0]["category"], "model_identity")
        self.assertEqual(result["candidate_score_records"], [])

    def test_raw_and_accepted_binding_tamper_detected(self):
        self.execute(threshold=1)
        path = self.path / "capture" / "0001.accepted.json"
        original = path.read_text(); value = json.loads(original)
        value["raw_sha256"] = "changed"; path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.replay(threshold=1)
        path.write_text(original)
        path = self.path / "capture" / "0001.raw.bin"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError): self.replay(threshold=1)

    def test_accounting_tamper_detected(self):
        self.execute(threshold=1)
        path = self.path / "capture" / "0001.accounting.json"
        value = run.read_json(path); value["undiscounted_token_estimate_microusd"] += 1
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.replay(threshold=1)

    def test_orphan_capture_detected(self):
        self.execute(threshold=1)
        (self.path / "capture" / "0002.raw.bin").write_bytes(b"orphan")
        with self.assertRaises(ValueError): self.replay(threshold=1)

    def test_reserved_attempt_without_payload_is_unknown(self):
        original = run.guard._write_exclusive
        def fail(path, value):
            if path.name.endswith(".payload.json"): raise OSError("fixture")
            original(path, value)
        with patch.object(run.guard, "_write_exclusive", side_effect=fail):
            with self.assertRaises(OSError): self.execute()
        result = self.replay()
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["accounting"]["unknown_charge_attempts"], 1)
        self.assertEqual(result["terminal"], "interrupted_unknown_delivery_or_charge")

    def test_report_write_failure_does_not_lose_successful_captures(self):
        original = run.write_json
        def fail(path, value):
            if path.name == "report.json": raise OSError("fixture")
            original(path, value)
        with patch.object(run, "write_json", side_effect=fail):
            with self.assertRaises(OSError): self.execute(threshold=1)
        result = self.replay(threshold=1)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["accepted_judgments"], 1)


if __name__ == "__main__":
    unittest.main()
