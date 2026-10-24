import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import scoring_s33 as exp
from benchmark.provenance import sha256_json
from benchmark.providers.observed_http import DiagnosticRequestError

ROOT = Path(__file__).resolve().parents[1]


class S33Tests(unittest.TestCase):
    def setUp(self):
        self.policy, self.full, self.packets, self.controls = exp.inputs(ROOT)
        self.approved = sha256_json(exp.check_manifest(ROOT))

    def encode(self, provider, model, judgment):
        content = [{"type": "text" if provider == "gemini" else "output_text", "text": json.dumps(judgment)}]
        field, kind = ("steps", "model_output") if provider == "gemini" else ("output", "message")
        return {"status": "completed", "model": model, field: [{"type": kind, "content": content}]}

    def reply(self, provider, model, key, packet, instruction, timeout):
        self.assertEqual(timeout, 240)
        stage = packet["scoring_stage"]
        self.assertEqual(instruction, (ROOT / exp.PROMPTS[stage]).read_text())
        name = next(k for k, p in self.packets.items() if p == packet)
        rows = [{"stage_id": stage, "requirement_index": a["requirement_index"], "status": "met",
                 "response_evidence": packet["transcript"][1 if stage == "initial" else 3]["content"],
                 "rationale": "Synthetic software fixture, not a clinical judgment."} for a in packet["criterion_anchors"]]
        errors = []
        if stage == "initial" and "TRIAGE-020" in name:
            rows[2]["status"] = "partial"
        if stage == "update":
            if name.endswith("__partial"):
                rows[2]["status"] = "missed"
                if "TRIAGE-020" in name:
                    rows[1]["status"] = "partial"
            if name.endswith("__unsafe"):
                for row in rows: row["status"] = "missed"
                e = next(e for e in packet["turn_labels"][0]["critical_errors"] if e["id"] == self.controls[name])
                errors = [{"stage_id": stage, "error_id": e["id"], "severity": e["severity"],
                           "rationale": "Configured software error fixture."}]
        judgment = {"criterion_assessments": rows, "critical_errors": errors}
        if stage == "update":
            judgment["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure",
                "response_evidence": "", "new_fact": "Software fixture update.", "independent_consequence_or_failure": "",
                "overlap_note": "Software fixture, no extra numeric deduction."} for d in ("safety", "revision")]
        return self.encode(provider, model, judgment), 1

    def judgment(self, key):
        packet = self.packets[key]
        raw, _ = self.reply("gemini", "unit-model", "unused", packet,
                            (ROOT / exp.PROMPTS[packet["scoring_stage"]]).read_text(), 240)
        return exp.base.parse_response(raw, "gemini")

    def altered(self, change):
        calls = 0
        def reply(*args):
            nonlocal calls
            calls += 1
            raw, latency = self.reply(*args)
            j = exp.base.parse_response(raw, args[0])
            change(j, calls, args[3])
            return self.encode(args[0], args[1], j), latency
        return reply

    def mocks(self, handler=None):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(exp, "read_setting", return_value="unit-test-only-key"))
        request = stack.enter_context(patch.object(exp, "request", side_effect=handler or self.reply))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        return stack, request

    def run_fake(self, output):
        return exp.run(ROOT, output, ROOT / "not-read", 48, self.approved)

    def change_file(self, path, mutate):
        data = json.loads(path.read_text()); mutate(data); path.write_text(json.dumps(data))

    def transport_error(self):
        return DiagnosticRequestError({"version": "transport-diagnostic-v1", "category": "timeout", "http_status": None,
            "elapsed_ms": 240001, "delivery": "unknown", "attempts": 1, "automatic_retries": 0})

    def test_frozen_scope_and_unchanged_historical_answers_and_arithmetic(self):
        exp.previous.check_manifest(ROOT)
        old, packets, controls = exp.previous.inputs(ROOT)
        self.assertEqual(self.controls, controls)
        for key in ("stage_weights", "criterion_credit", "critical_error_rules", "provisional_pass_threshold", "judges"):
            self.assertEqual(self.policy[key], old[key])
        for key, packet in self.full.items():
            self.assertEqual(packet["transcript"], packets[key]["transcript"])
            self.assertEqual(packet["turn_labels"], packets[key]["turn_labels"])
            changed = [(a["stage_id"], a["requirement_index"]) for a, b in
                       zip(packet["criterion_anchors"], packets[key]["criterion_anchors"]) if a != b]
            self.assertEqual(changed, [("initial", 3), ("update", 2)] if "TRIAGE-020" in key else [])

    def test_initial_isolation_allowlist_and_shared_answer(self):
        for key, p in self.packets.items():
            self.assertEqual(set(p), {"case_id", "case_content_hash", "language", "scoring_stage", "transcript",
                                     "turn_labels", "criterion_anchors", "level_definitions"})
            stage = p["scoring_stage"]
            self.assertEqual(len(p["transcript"]), 2 if stage == "initial" else 4)
            self.assertEqual({a["stage_id"] for a in p["criterion_anchors"]}, {stage})
            self.assertEqual([t["stage_id"] for t in p["turn_labels"]], [stage])
            if stage == "initial":
                for kind in ("safe", "partial", "unsafe"):
                    full_key = key.rsplit("__", 1)[0] + "__" + kind
                    self.assertEqual(p["transcript"], self.full[full_key]["transcript"][:2])
                self.assertNotIn("dimension_observations", exp.schema(p)["properties"])
            else:
                self.assertIn("dimension_observations", exp.schema(p)["properties"])

    def test_schedule_has_32_first_16_repeat_calls_and_bound_schemas(self):
        schedule = exp.schedule(self.policy, self.packets)
        self.assertEqual(len(schedule), 48)
        self.assertEqual([phase for phase, _, _ in schedule], ["first"] * 32 + ["repeat"] * 16)
        self.assertEqual([self.packets[k]["scoring_stage"] for _, k, _ in schedule],
                         ["initial"] * 8 + ["update"] * 24 + ["initial"] * 8 + ["update"] * 8)
        self.assertTrue(all(k.endswith(("__initial", "__partial")) for phase, k, _ in schedule if phase == "repeat"))
        frozen = exp.check_manifest(ROOT)
        self.assertEqual(len(frozen["stage_packets"]), 16)
        self.assertEqual(len(frozen["full_packets"]), 12)
        self.assertEqual(frozen["schedule_sha256"], sha256_json(schedule))
        self.assertIn("tests/test_scoring_s33.py", frozen["files"])

    def test_provider_payload_schema_is_stage_specific_keyless_and_unpinned(self):
        for stage in ("initial", "update"):
            packet = next(p for p in self.packets.values() if p["scoring_stage"] == stage)
            for spec in self.policy["judges"]:
                with patch.object(exp, "post_json_observed", return_value=({}, 1)) as http:
                    exp.request(spec["provider"], spec["model"], "synthetic-secret", packet, "instruction", 240)
                    args, kwargs = http.call_args
                    payload = args[1]
                    self.assertEqual(kwargs["retries"], 0)
                    self.assertEqual(kwargs["timeout"], 240)
                    self.assertFalse(payload["store"])
                    self.assertNotIn("synthetic-secret", json.dumps(payload))
                    actual = payload["response_format"]["schema"] if spec["provider"] == "gemini" else payload["text"]["format"]["schema"]
                    self.assertEqual(actual, exp.schema(packet))
                    for field in ("temperature", "top_p", "seed"):
                        self.assertNotIn(field, payload)

    def test_initial_contract_rejects_future_quotes_extra_observations_and_changed_errors(self):
        key = "HC-MT-TRIAGE-020__en__initial"
        good = self.judgment(key)
        error = self.packets[key]["turn_labels"][0]["critical_errors"][0]
        for mutate in (
            lambda j: j.update(dimension_observations=[]),
            lambda j: j["criterion_assessments"][0].update(stage_id="update"),
            lambda j: j["criterion_assessments"][0].update(requirement_index=True),
            lambda j: j["criterion_assessments"][0].update(response_evidence=self.full["HC-MT-TRIAGE-020__en__safe"]["transcript"][3]["content"]),
            lambda j: j["criterion_assessments"][0].update(response_evidence="", status="partial"),
            lambda j: j["criterion_assessments"].reverse(),
            lambda j: j["criterion_assessments"].pop(),
            lambda j: j.update(critical_errors=[{"stage_id": "initial", "error_id": error["id"], "severity": 3, "rationale": "test"}]),
            lambda j: j.update(critical_errors=[{"stage_id": "update", "error_id": error["id"], "severity": error["severity"], "rationale": "test"}]),
        ):
            j = deepcopy(good); mutate(j)
            with self.assertRaises(ValueError): exp.validate(j, self.packets[key])

    def test_initial_avoidance_empty_quote_and_duplicate_error_rules_match_existing_contract(self):
        key = "HC-MT-TRIAGE-018__en__initial"
        j = self.judgment(key)
        j["criterion_assessments"][2]["response_evidence"] = ""
        exp.validate(j, self.packets[key])
        e = self.packets[key]["turn_labels"][0]["critical_errors"][0]
        row = {"stage_id": "initial", "error_id": e["id"], "severity": e["severity"], "rationale": "software"}
        j["critical_errors"] = [row]
        exp.validate(j, self.packets[key])
        j["critical_errors"].append(deepcopy(row))
        with self.assertRaises(ValueError): exp.validate(j, self.packets[key])

    def test_update_cannot_rejudge_initial_or_join_quotes(self):
        key = "HC-MT-TRIAGE-020__zh-Hans__safe"
        good = self.judgment(key)
        for mutate in (
            lambda j: j["criterion_assessments"][0].update(stage_id="initial"),
            lambda j: j["dimension_observations"][0].update(response_evidence="出现严重新症状应及时就医。 / 新出现眼周肿胀、视力变化或严重头痛应及时评估。"),
            lambda j: j["dimension_observations"][0].update(response_evidence="Helpful safety advice, paraphrased."),
        ):
            j = deepcopy(good); mutate(j)
            with self.assertRaises(ValueError): exp.validate(j, self.packets[key])

    def test_combination_preserves_initial_errors_and_exact_formula(self):
        key = "HC-MT-TRIAGE-020__en__safe"
        initial = self.judgment("HC-MT-TRIAGE-020__en__initial")
        update = self.judgment(key)
        error = self.full[key]["turn_labels"][0]["critical_errors"][0]
        initial["critical_errors"] = [{"stage_id": "initial", "error_id": error["id"], "severity": error["severity"], "rationale": "software fixture"}]
        snapshot = deepcopy((initial, update))
        j, score = exp.combine(initial, update, self.full[key], self.policy)
        old_policy = exp.previous.inputs(ROOT)[0]
        old_score = exp.base.score(j, self.full[key], old_policy)
        score.pop("score_version"); old_score.pop("score_version")
        self.assertEqual(score, old_score)
        self.assertEqual((initial, update), snapshot)
        self.assertEqual(j["critical_errors"], initial["critical_errors"])

    def test_bad_cap_ack_and_output_fail_before_keys_or_calls(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp, patch.object(exp, "read_setting") as keys, patch.object(exp, "request") as request:
            output = Path(tmp) / "run"
            for cap, ack in ((48, None), (48, "wrong"), (32, self.approved), (True, self.approved), (49, self.approved)):
                with self.assertRaises(ValueError): exp.run(ROOT, output, ROOT / "not-read", cap, ack)
            for path in (Path(tmp), ROOT / "not-work-s33"):
                with self.assertRaises(ValueError): exp.run(ROOT, path, ROOT / "not-read", 48, self.approved)
            self.assertFalse(output.exists()); keys.assert_not_called(); request.assert_not_called()

    def test_plan_never_reads_credentials_or_calls_provider(self):
        with patch.object(exp, "read_setting") as keys, patch.object(exp, "request") as request:
            report = exp.plan(ROOT)
            self.assertEqual(report["maximum_calls"], 48)
            self.assertEqual(report["protocol_sha256"], self.approved)
            keys.assert_not_called(); request.assert_not_called()

    def test_complete_mock_panel_audits_and_never_authorizes_candidates(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks()
            with stack:
                output = Path(tmp) / "run"; result = self.run_fake(output)
                self.assertEqual(request.call_count, 48)
                self.assertEqual(result["valid_stage_judgments"], 48)
                self.assertEqual(result["derived_conversation_scores"], 32)
                self.assertEqual(result["boundary_hypothesis_matches"], 24)
                self.assertEqual(result["exact_stage_vector_repeats"], 16)
                for field in ("unsafe_errors_detected", "strict_answer_order_groups", "exact_partial_repeats"):
                    self.assertEqual(result[field], 8)
                self.assertTrue(result["ready_to_design_small_candidate_pilot"])
                self.assertFalse(result["candidate_pilot_authorized"]); self.assertFalse(result["calibration_complete"])
                self.assertEqual(result, exp.audit(ROOT, output))
                with self.assertRaises(ValueError): self.run_fake(output)
                self.assertEqual(request.call_count, 48)

    def test_initial_unclear_propagates_to_each_profile_and_repeat_without_point_scores(self):
        def change(j, _, packet):
            if packet == self.packets["HC-MT-TRIAGE-020__en__initial"]:
                j["criterion_assessments"][2]["status"] = "unclear"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(self.altered(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                uncertain = [c for c in result["score_cells"] if "TRIAGE-020__en__" in c["packet"]]
                self.assertEqual(len(uncertain), 8)
                self.assertTrue(all(c["score"]["point_score"] is None and c["score"]["provisional_pass"] is None for c in uncertain))
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_changed_initial_repeat_cannot_be_hidden_by_reusing_first_initial(self):
        def change(j, n, _):
            if n == 33: j["criterion_assessments"][0]["status"] = "partial"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(self.altered(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(result["exact_stage_vector_repeats"], 15)
                self.assertEqual(result["exact_partial_repeats"], 7)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_equal_numeric_score_changed_update_vector_still_fails_repeat(self):
        def change(j, n, _):
            if n == 41:
                j["criterion_assessments"][0]["status"] = "missed"
                j["criterion_assessments"][2]["status"] = "met"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(self.altered(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertTrue(result["repeat_checks"][0]["score_equal"])
                self.assertFalse(result["repeat_checks"][0]["vector_equal"])
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_boundary_hypothesis_disagreement_is_retained_not_repaired(self):
        def change(j, _, packet):
            if packet == self.packets["HC-MT-TRIAGE-020__en__initial"]:
                j["criterion_assessments"][2]["status"] = "met"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(self.altered(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(request.call_count, 48)
                self.assertEqual(result["boundary_hypothesis_matches"], 20)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_missing_unsafe_error_blocks_gate(self):
        def change(j, _, packet):
            if packet == self.packets["HC-MT-TRIAGE-020__en__unsafe"]: j["critical_errors"] = []
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(self.altered(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(result["unsafe_errors_detected"], 6)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_concern_blocks_gate_without_extra_numeric_penalty(self):
        def change(j, _, packet):
            if packet == self.packets["HC-MT-TRIAGE-020__en__safe"]: j["dimension_observations"][0]["decision"] = "unclear"
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(self.altered(change))
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(result["independent_dimension_concern_cells_safe_or_partial"], 2)
                self.assertEqual(result["strict_answer_order_groups"], 8)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_transport_stop_before_update_does_not_invent_conversation_score(self):
        calls = 0
        def handler(*args):
            nonlocal calls
            calls += 1
            if calls == 9: raise self.transport_error()
            return self.reply(*args)
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(handler)
            with stack:
                output = Path(tmp) / "run"; result = self.run_fake(output)
                self.assertEqual((result["attempted_calls"], result["valid_stage_judgments"], result["derived_conversation_scores"]), (9, 8, 0))
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])
                with self.assertRaises(ValueError): self.run_fake(output)
                self.assertEqual(request.call_count, 9)

    def test_stop_during_repeat_preserves_only_available_combined_pairs(self):
        calls = 0
        def handler(*args):
            nonlocal calls
            calls += 1
            if calls == 43: raise self.transport_error()
            return self.reply(*args)
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(handler)
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(result["valid_stage_judgments"], 42)
                self.assertEqual(result["partial_repeat_pairs"], 2)
                self.assertFalse(result["ready_to_design_small_candidate_pilot"])

    def test_invalid_model_json_nonobject_and_latency_stop_after_one_raw_reply(self):
        for failure in ("model", "json", "nonobject", "latency", "boolean"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
                def handler(*args):
                    raw, latency = self.reply(*args)
                    if failure == "model": raw["model"] = "unexpected-model"
                    elif failure == "json": raw["steps"][0]["content"][0]["text"] = "not-json"
                    elif failure == "nonobject": raw = []
                    elif failure == "latency": latency = -1
                    else: latency = True
                    return raw, latency
                stack, request = self.mocks(handler)
                with stack:
                    output = Path(tmp) / "run"; result = self.run_fake(output)
                    self.assertEqual(request.call_count, 1)
                    self.assertEqual(result["valid_stage_judgments"], 0)
                    self.assertEqual(result["stopped"]["kind"], "response_validation_failure")
                    self.assertTrue((output / "01.response.json").exists())

    def test_saved_judgment_raw_identity_and_latency_are_bound(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                path = output / "01.judgment.json"; original = path.read_text()
                for mutate in (lambda r: r["judgment"]["criterion_assessments"][0].update(status="partial"),
                               lambda r: r.update(latency_ms=True), lambda r: r.update(score=80),
                               lambda r: r.update(model_returned="other")):
                    self.change_file(path, mutate)
                    with self.assertRaises(ValueError): exp.audit(ROOT, output)
                    path.write_text(original)
                self.change_file(output / "01.response.json", lambda r: r.update(model="other"))
                with self.assertRaises(ValueError): exp.audit(ROOT, output)

    def test_artifact_prefix_ack_and_completion_are_verified(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                for filename, mutate in (
                    ("external_call_acknowledgment.json", lambda r: r.update(maximum_calls=32)),
                    ("complete.json", lambda r: r.update(judge_calls=32)),
                    ("01.attempt.json", lambda r: r.update(phase="repeat")),
                    ("manifest.json", lambda r: r.update(version="other")),
                ):
                    path = output / filename; original = path.read_text(); self.change_file(path, mutate)
                    with self.assertRaises(ValueError): exp.audit(ROOT, output)
                    path.write_text(original)
                (output / "01.judgment.json").rename(output / "49.judgment.json")
                with self.assertRaisesRegex(ValueError, "contiguous"): exp.audit(ROOT, output)

    def test_unsafe_stop_marker_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(self.transport_error())
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                self.change_file(output / "stopped.json", lambda r: r.update(message="unexpected raw error text"))
                with self.assertRaises(ValueError): exp.audit(ROOT, output)


if __name__ == "__main__":
    unittest.main()
