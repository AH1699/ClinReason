import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import scoring_s31 as exp
from benchmark import boundary_s27
from benchmark.provenance import sha256_json
from benchmark.providers.observed_http import DiagnosticRequestError

ROOT = Path(__file__).resolve().parents[1]


class S31IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.policy, self.packets, self.controls = exp.inputs(ROOT)
        self.approved = sha256_json(exp.check_manifest(ROOT))

    def encode(self, provider, model, judgment):
        raw = {"status": "completed", "model": model}
        if provider == "gemini":
            raw["steps"] = [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(judgment)}]}]
        else:
            raw["output"] = [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(judgment)}]}]
        return raw

    def reply(self, provider, model, key, packet, instruction, timeout):
        self.assertEqual(timeout, 240)
        name = next(k for k, p in self.packets.items() if p == packet)
        rows = [{"stage_id": a["stage_id"], "requirement_index": a["requirement_index"],
                 "status": "met", "response_evidence": packet["transcript"][1 if a["stage_id"] == "initial" else 3]["content"],
                 "rationale": "Synthetic software fixture; not a clinical judgment."}
                for a in packet["criterion_anchors"]]
        errors = []
        if name.endswith("__partial"):
            rows[-1]["status"] = "partial"
        if name.endswith("__unsafe"):
            for row in rows:
                if row["stage_id"] == "update":
                    row["status"] = "missed"
            error = next(e for t in packet["turn_labels"] for e in t["critical_errors"]
                         if e["id"] == self.controls[name])
            errors = [{"stage_id": "update", "error_id": error["id"], "severity": error["severity"],
                       "rationale": "Synthetic configured-error fixture."}]
        judgment = {"criterion_assessments": rows, "critical_errors": errors,
                    "dimension_observations": [{"dimension": d, "decision": "no_distinct_failure",
                        "response_evidence": "", "new_fact": "Synthetic update", "independent_consequence_or_failure": "",
                        "overlap_note": "No separate penalty in this fixture."} for d in ("safety", "revision")]}
        return self.encode(provider, model, judgment), 1

    def mocks(self, handler=None):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(exp, "read_setting", return_value="unit-test-only-key"))
        request = stack.enter_context(patch.object(exp, "request", side_effect=handler or self.reply))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        return stack, request

    def run_fake(self, output):
        return exp.run(ROOT, output, ROOT / "not-read", 32, self.approved)

    def change_json(self, path, change):
        obj = json.loads(path.read_text())
        change(obj)
        path.write_text(json.dumps(obj))

    def altered_reply(self, change):
        calls = 0
        def reply(*args):
            nonlocal calls
            calls += 1
            raw, latency = self.reply(*args)
            judgment = exp.base.parse_response(raw, args[0])
            change(judgment, calls, args[3])
            return self.encode(args[0], args[1], judgment), latency
        return reply

    def test_historical_freezes_and_unchanged_scoring(self):
        exp.base.check_manifest(ROOT)
        boundary_s27.check_manifest(ROOT)
        exp.previous.check_manifest(ROOT)
        exp.boundary.check_manifest(ROOT)
        old, old_packets, _ = exp.previous.inputs(ROOT)
        for key in old:
            if key not in {"version", "timeout_seconds", "anchor_path", "comparison", "advance_gate"}:
                self.assertEqual(old[key], self.policy[key])
        for key, packet in self.packets.items():
            self.assertEqual(packet["transcript"], old_packets[key]["transcript"])
            self.assertEqual(packet["turn_labels"], old_packets[key]["turn_labels"])
            changed = [(a["stage_id"], a["requirement_index"]) for a, b in
                       zip(packet["criterion_anchors"], old_packets[key]["criterion_anchors"]) if a != b]
            self.assertEqual(changed, [("update", 1), ("update", 3)] if "TRIAGE-020" in key else [])
            raw, _ = self.reply("gemini", "unit-model", "unused", packet, "test", 240)
            judgment = exp.base.parse_response(raw, "gemini")
            new_score = exp.base.score(judgment, packet, self.policy)
            old_score = exp.base.score(judgment, old_packets[key], old)
            new_score.pop("score_version"); old_score.pop("score_version")
            self.assertEqual(new_score, old_score)

    def test_schedule_freeze_schema_and_blinding(self):
        plan = exp.schedule(self.policy, self.packets)
        self.assertEqual(len(plan), 32)
        self.assertEqual([phase for phase, _, _ in plan], ["first"] * 24 + ["repeat"] * 8)
        self.assertEqual({key for phase, key, _ in plan if phase == "repeat"},
                         {key for key in self.packets if key.endswith("__partial")})
        frozen = exp.check_manifest(ROOT)
        self.assertEqual(frozen["schedule_sha256"], sha256_json(plan))
        self.assertEqual(len(frozen["output_schema_sha256"]), 12)
        for packet in self.packets.values():
            for hidden in ("answer_type", "expected_unsafe_error_id", "expected_statuses", "score_target", "profile"):
                self.assertNotIn(hidden, packet)
        self.assertIn("tests/test_scoring_s31.py", frozen["files"])

    def test_transport_payload_preserves_contract_and_has_no_retries(self):
        packet = next(iter(self.packets.values()))
        for spec in self.policy["judges"]:
            with patch.object(exp, "post_json_observed", return_value=({}, 1)) as http:
                exp.request(spec["provider"], spec["model"], "synthetic-secret", packet, "instruction", 240)
                args, kwargs = http.call_args
                payload = args[1]
                self.assertEqual(kwargs["timeout"], 240)
                self.assertEqual(kwargs["retries"], 0)
                self.assertFalse(payload["store"])
                self.assertNotIn("synthetic-secret", json.dumps(payload))
                actual_schema = (payload["response_format"]["schema"] if spec["provider"] == "gemini"
                                 else payload["text"]["format"]["schema"])
                self.assertEqual(actual_schema, exp.base.schema(packet))
                for field in ("temperature", "top_p", "seed"):
                    self.assertNotIn(field, payload)

    def test_bad_cap_ack_and_output_rejected_before_secrets_or_network(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp, \
                patch.object(exp, "read_setting") as secrets, patch.object(exp, "request") as request:
            output = Path(tmp) / "run"
            for cap, ack in ((32, None), (32, "wrong"), (33, self.approved), (True, self.approved), (0, self.approved)):
                with self.assertRaisesRegex(ValueError, "approved protocol"):
                    exp.run(ROOT, output, ROOT / "not-read", cap, ack)
            with self.assertRaises(ValueError):
                exp.run(ROOT, ROOT / "out-of-scope-s31", ROOT / "not-read", 32, self.approved)
            with self.assertRaises(ValueError):
                exp.run(ROOT, Path(tmp), ROOT / "not-read", 32, self.approved)
            self.assertFalse(output.exists())
            secrets.assert_not_called(); request.assert_not_called()

    def test_complete_mock_panel_and_no_automatic_candidate_authority(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks()
            with stack:
                output = Path(tmp) / "run"
                result = self.run_fake(output)
                self.assertEqual(request.call_count, 32)
                self.assertEqual(result["valid_judgments"], 32)
                for field in ("unsafe_errors_detected", "strict_answer_order_groups", "exact_partial_repeats"):
                    self.assertEqual(result[field], 8)
                self.assertTrue(result["ready_to_design_small_candidate_pilot"])
                self.assertFalse(result["candidate_pilot_authorized"])
                self.assertFalse(result["calibration_complete"])
                self.assertEqual(result, exp.audit(ROOT, output))
                with self.assertRaisesRegex(ValueError, "fresh"):
                    self.run_fake(output)
                self.assertEqual(request.call_count, 32)

    def test_unclear_is_valid_but_not_a_point_repeat_or_strict_order(self):
        def change(j, _, packet):
            if packet == self.packets["HC-MT-TRIAGE-020__en__partial"]:
                j["criterion_assessments"][-1]["status"] = "unclear"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(self.altered_reply(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(request.call_count, 32)
                self.assertEqual(result["strict_answer_order_groups"], 6)
                self.assertEqual(result["exact_partial_repeats"], 6)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])
                unclear = [r for r in result["cells"] if r["score"]["unclear_criterion"]]
                self.assertEqual(len(unclear), 4)
                self.assertTrue(all(r["score"]["point_score"] is None and r["score"]["provisional_pass"] is None for r in unclear))

    def test_repeat_flip_cannot_pass_even_when_first_order_passes(self):
        def change(j, n, _):
            if n == 25:
                j["criterion_assessments"][-1]["status"] = "missed"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(self.altered_reply(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(request.call_count, 32)
                self.assertEqual(result["strict_answer_order_groups"], 8)
                self.assertEqual(result["exact_partial_repeats"], 7)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_equal_total_but_changed_criterion_vector_fails_repeat(self):
        def change(j, n, _):
            if n == 25:
                j["criterion_assessments"][-1]["status"] = "met"
                j["criterion_assessments"][-2]["status"] = "partial"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(self.altered_reply(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                check = result["repeat_checks"][0]
                self.assertTrue(check["score_equal"])
                self.assertFalse(check["vector_equal"])
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_missing_unsafe_error_is_retained_without_extra_calls(self):
        def change(j, _, packet):
            if packet == self.packets["HC-MT-TRIAGE-020__en__unsafe"]:
                j["critical_errors"] = []
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(self.altered_reply(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(request.call_count, 32)
                self.assertEqual(result["unsafe_errors_detected"], 6)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_independent_concern_holds_gate_without_duplicate_numeric_penalty(self):
        def change(j, _, packet):
            if packet == self.packets["HC-MT-TRIAGE-020__en__safe"]:
                j["dimension_observations"][0]["decision"] = "unclear"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(self.altered_reply(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(request.call_count, 32)
                self.assertEqual(result["independent_dimension_concern_cells_safe_or_partial"], 2)
                safe = [r for r in result["cells"] if r["packet"] == "HC-MT-TRIAGE-020__en__safe"]
                self.assertEqual([r["score"]["point_score"] for r in safe], [100, 100])
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_transport_stop_records_only_safe_fields_and_cannot_resume(self):
        diagnostic = {"version": "transport-diagnostic-v1", "category": "timeout", "http_status": None,
                      "elapsed_ms": 240001, "delivery": "unknown", "attempts": 1, "automatic_retries": 0}
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(DiagnosticRequestError(diagnostic))
            with stack:
                output = Path(tmp) / "run"
                result = self.run_fake(output)
                self.assertEqual((result["attempted_calls"], result["valid_judgments"]), (1, 0))
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])
                self.assertEqual(result["stopped"]["diagnostic"], diagnostic)
                with self.assertRaises(ValueError):
                    self.run_fake(output)
                self.assertEqual(request.call_count, 1)
                self.change_json(output / "stopped.json", lambda x: x.update(message="untrusted-free-text"))
                with self.assertRaisesRegex(ValueError, "unsafe S31"):
                    exp.audit(ROOT, output)

    def test_stop_mid_repeat_keeps_prefix_not_a_completed_panel(self):
        calls = 0
        def handler(*args):
            nonlocal calls
            calls += 1
            if calls == 27:
                raise DiagnosticRequestError({"version": "transport-diagnostic-v1", "category": "network_error",
                    "http_status": None, "elapsed_ms": 1, "delivery": "unknown", "attempts": 1, "automatic_retries": 0})
            return self.reply(*args)
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(handler)
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual((request.call_count, result["valid_judgments"], result["partial_repeat_pairs"]), (27, 26, 2))
                self.assertEqual(result["status"], "incomplete_saved_prefix")
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_model_bad_json_nonobject_and_invalid_latency_stop_with_raw_saved(self):
        for failure in ("model", "json", "nonobject", "negative_latency", "boolean_latency"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
                def handler(*args):
                    raw, latency = self.reply(*args)
                    if failure == "model": raw["model"] = "unrequested-model-alias"
                    elif failure == "json": raw["steps"][0]["content"][0]["text"] = "not-json"
                    elif failure == "nonobject": raw = []
                    elif failure == "negative_latency": latency = -1
                    else: latency = True
                    return raw, latency
                stack, request = self.mocks(handler)
                with stack:
                    output = Path(tmp) / "run"
                    result = self.run_fake(output)
                    self.assertEqual(request.call_count, 1)
                    self.assertEqual(result["stopped"]["kind"], "response_validation_failure")
                    self.assertTrue((output / "01.response.json").exists())
                    self.assertEqual(result["valid_judgments"], 0)

    def test_complete_judgment_contract_rejects_wrong_evidence_severity_or_order(self):
        packet = self.packets["HC-MT-TRIAGE-020__en__unsafe"]
        raw, _ = self.reply("gemini", "model", "unused", packet, "instruction", 240)
        good = exp.base.parse_response(raw, "gemini")
        for mutate in (
            lambda j: j["criterion_assessments"].reverse(),
            lambda j: j["criterion_assessments"].pop(),
            lambda j: j["criterion_assessments"][0].update(response_evidence=packet["transcript"][3]["content"]),
            lambda j: j["criterion_assessments"][0].update(status="met", response_evidence=""),
            lambda j: j["critical_errors"][0].update(severity=3),
            lambda j: j["critical_errors"].append(deepcopy(j["critical_errors"][0])),
            lambda j: j["dimension_observations"].reverse(),
            lambda j: j.update(score=80),
        ):
            altered = deepcopy(good); mutate(altered)
            with self.assertRaises(ValueError): exp.base.score(altered, packet, self.policy)

    def test_saved_score_raw_latency_and_extra_fields_are_bound(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"
                self.run_fake(output)
                path = output / "01.judgment.json"
                original = path.read_text()
                for mutate in (lambda j: j["score"].update(point_score=12),
                               lambda j: j["judgment"]["criterion_assessments"][0].update(rationale="edited"),
                               lambda j: j.update(latency_ms=-1), lambda j: j.update(extra="unexpected")):
                    self.change_json(path, mutate)
                    with self.assertRaisesRegex(ValueError, "mismatch"): exp.audit(ROOT, output)
                    path.write_text(original)
                self.change_json(output / "01.response.json", lambda j: j.update(model="tampered"))
                with self.assertRaisesRegex(ValueError, "mismatch"): exp.audit(ROOT, output)

    def test_ack_manifest_and_attempt_schedule_tampering_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                for name, mutate in (
                    ("external_call_acknowledgment.json", lambda j: j.update(maximum_calls=33)),
                    ("manifest.json", lambda j: j.update(schedule_sha256="changed")),
                    ("01.attempt.json", lambda j: j.update(timeout_seconds=120))):
                    path = output / name; original = path.read_text(); self.change_json(path, mutate)
                    with self.assertRaises(ValueError): exp.audit(ROOT, output)
                    path.write_text(original)

    def test_orphan_or_noncontiguous_artifacts_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                extra = output / "33.response.json"; extra.write_text("{}")
                with self.assertRaisesRegex(ValueError, "counts"): exp.audit(ROOT, output)
                extra.unlink()
                (output / "01.response.json").rename(output / "00.response.json")
                with self.assertRaisesRegex(ValueError, "prefix"): exp.audit(ROOT, output)

    def test_missing_completion_marker_cannot_pass(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                (output / "complete.json").unlink()
                result = exp.audit(ROOT, output)
                self.assertEqual(result["valid_judgments"], 32)
                self.assertEqual(result["status"], "incomplete_saved_prefix")
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_false_completion_on_stopped_run_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(lambda *args: ({"status": "failed", "model": "bad"}, 1))
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                (output / "complete.json").write_text(json.dumps({"judge_calls": 32, "candidate_calls": 0}))
                with self.assertRaises(ValueError): exp.audit(ROOT, output)


if __name__ == "__main__":
    unittest.main()
