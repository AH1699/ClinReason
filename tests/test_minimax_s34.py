import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import minimax_s34 as exp
from benchmark.provenance import sha256_json
from benchmark.providers.observed_http import DiagnosticRequestError

ROOT = Path(__file__).resolve().parents[1]


class S34Tests(unittest.TestCase):
    def setUp(self):
        self.policy, self.score_policy, self.templates, self.levels = exp.inputs(ROOT)
        self.approved = sha256_json(exp.check_manifest(ROOT))

    def reply(self, spec, key, packet, instruction):
        if spec["kind"] == "candidate":
            return {"model": spec["model"], "base_resp": {"status_code": 0}, "choices": [{"finish_reason": "stop",
                "message": {"content": f"Software fixture answer for {spec['case_key']} at {spec['stage']}.",
                            "reasoning_content": "HIDDEN_THINKING_SENTINEL"}}]}, 1
        stage = spec["stage"]
        judgment = {"criterion_assessments": [{"stage_id": stage, "requirement_index": a["requirement_index"],
            "status": "met", "response_evidence": packet["transcript"][1 if stage == "initial" else 3]["content"],
            "rationale": "Software fixture, not clinical assessment."} for a in packet["criterion_anchors"]], "critical_errors": []}
        if stage == "update":
            judgment["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure", "response_evidence": "",
                "new_fact": "Software fixture update.", "independent_consequence_or_failure": "", "overlap_note": "Software fixture."}
                for d in ("safety", "revision")]
        return self.encode(spec, judgment), 1

    def encode(self, spec, judgment):
        if spec["provider"] == "gemini":
            return {"model": spec["model"], "status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(judgment)}]}]}
        return {"model": spec["model"], "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(judgment)}]}]}

    def mocks(self, handler=None):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(exp, "read_setting", return_value="test-key-not-real"))
        request = stack.enter_context(patch.object(exp, "request", side_effect=handler or self.reply))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        return stack, request

    def run_fake(self, output):
        return exp.run(ROOT, output, ROOT / "not-read", 24, self.approved)

    def mutate(self, path, change):
        obj = json.loads(path.read_text()); change(obj); path.write_text(json.dumps(obj))

    def test_schedule_scope_and_separate_control_gate(self):
        steps = exp.schedule(self.policy, self.score_policy)
        self.assertEqual(len(steps), 24)
        self.assertEqual(sum(s["kind"] == "candidate" for s in steps), 8)
        self.assertEqual([s["kind"] for s in steps[:6]], ["candidate"] * 2 + ["judge"] * 4)
        self.assertEqual([s["stage"] for s in steps[:6]], ["initial", "update", "initial", "initial", "update", "update"])
        self.assertEqual(exp.scoring.plan(ROOT)["maximum_calls"], 48)
        self.assertEqual(exp.plan(ROOT)["combined_ceiling_with_s33"], 72)

    def test_candidate_only_sees_visible_user_messages_and_own_answer(self):
        instruction = exp.instructions(ROOT)["candidate"]
        steps = exp.schedule(self.policy, self.score_policy)
        initial = exp.context(steps[0], self.templates, {}, self.levels, instruction)
        self.assertEqual(set(initial), {"model", "messages", "max_completion_tokens", "reasoning_split"})
        self.assertEqual(initial["messages"], [{"role": "system", "content": instruction}, self.templates[steps[0]["case_key"]]["transcript"][0]])
        answers = {(steps[0]["case_key"], "initial"): {"text": "Own answer only"}}
        update = exp.context(steps[1], self.templates, answers, self.levels, instruction)
        self.assertEqual([m["role"] for m in update["messages"]], ["system", "user", "assistant", "user"])
        self.assertEqual(update["messages"][2]["content"], "Own answer only")
        self.assertNotIn(self.templates[steps[0]["case_key"]]["transcript"][1]["content"], json.dumps(update))
        self.assertNotIn("critical_requirements", json.dumps(update))
        self.assertEqual(update["max_completion_tokens"], 8192)
        self.assertTrue(update["reasoning_split"])

    def test_judge_blinding_stage_isolation_and_no_reasoning_leak(self):
        observed = []
        def handler(spec, key, packet, instruction):
            observed.append((spec, deepcopy(packet)))
            return self.reply(spec, key, packet, instruction)
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(handler)
            with stack: self.run_fake(Path(tmp) / "run")
        for spec, packet in observed:
            self.assertNotIn("HIDDEN_THINKING_SENTINEL", json.dumps(packet))
            if spec["kind"] == "judge":
                self.assertEqual(len(packet["transcript"]), 2 if spec["stage"] == "initial" else 4)
                self.assertNotIn("candidate_model", packet)
                self.assertNotIn("expected_status", packet)
                self.assertNotIn("transition_failure_mode", packet)
                self.assertNotIn("MiniMax", json.dumps(packet))

    def test_candidate_transport_is_single_attempt_and_secret_not_in_payload(self):
        spec = exp.schedule(self.policy, self.score_policy)[0]
        packet = exp.context(spec, self.templates, {}, self.levels, exp.instructions(ROOT)["candidate"])
        with patch.object(exp, "post_json_observed", return_value=({}, 1)) as http:
            exp.request(spec, "test-secret-sentinel", packet, "unused")
            args, kwargs = http.call_args
            self.assertEqual(args, (exp.ENDPOINT, packet))
            self.assertEqual(kwargs["retries"], 0)
            self.assertEqual(kwargs["timeout"], 240)
            self.assertNotIn("test-secret-sentinel", json.dumps(packet))

    def test_bad_cap_ack_output_rejected_before_credentials_or_network(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp, patch.object(exp, "read_setting") as keys, patch.object(exp, "request") as request:
            for cap, ack in ((24, None), (24, "wrong"), (25, self.approved), (True, self.approved)):
                with self.assertRaises(ValueError): exp.run(ROOT, Path(tmp) / "run", ROOT / "not-read", cap, ack)
            for output in (Path(tmp), ROOT / "not-work-s34"):
                with self.assertRaises(ValueError): exp.run(ROOT, output, ROOT / "not-read", 24, self.approved)
            keys.assert_not_called(); request.assert_not_called()

    def test_complete_mock_run_replays_raw_candidate_and_judge_outputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks()
            with stack:
                output = Path(tmp) / "run"; result = self.run_fake(output)
                self.assertEqual(request.call_count, 24)
                self.assertEqual(result["valid_candidate_turns"], 8)
                self.assertEqual(result["valid_judge_stages"], 16)
                self.assertEqual(result["complete_candidate_conversations"], 4)
                self.assertEqual(result["derived_conversation_judge_scores"], 8)
                self.assertEqual(result["status"], "complete_workflow_diagnostic")
                self.assertFalse(result["comparison_ready"]); self.assertFalse(result["calibration_complete"])
                self.assertFalse(result["s33_gate_overridden"])
                self.assertEqual(result, exp.audit(ROOT, output))
                with self.assertRaises(ValueError): self.run_fake(output)
                self.assertEqual(request.call_count, 24)

    def test_candidate_invalid_output_stops_without_judging_or_fallback(self):
        for failure in ("model", "length", "thinking", "empty", "provider_status", "latency"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
                def handler(*args):
                    raw, latency = self.reply(*args)
                    if failure == "model": raw["model"] = "another-model"
                    elif failure == "length": raw["choices"][0]["finish_reason"] = "length"
                    elif failure == "thinking": raw["choices"][0]["message"]["content"] = "<think>private</think> answer"
                    elif failure == "empty": raw["choices"][0]["message"]["content"] = ""
                    elif failure == "provider_status": raw["base_resp"]["status_code"] = 1008
                    else: latency = True
                    return raw, latency
                stack, request = self.mocks(handler)
                with stack:
                    output = Path(tmp) / "run"; result = self.run_fake(output)
                    self.assertEqual(request.call_count, 1)
                    self.assertEqual(result["valid_candidate_turns"], 0)
                    self.assertEqual(result["valid_judge_stages"], 0)
                    self.assertEqual(result["stopped"]["kind"], "response_validation_failure")
                    self.assertTrue((output / "01.response.json").exists())

    def test_transport_stop_preserves_unknown_delivery_and_no_resume(self):
        error = DiagnosticRequestError({"version": "transport-diagnostic-v1", "category": "timeout", "http_status": None,
            "elapsed_ms": 240000, "delivery": "unknown", "attempts": 1, "automatic_retries": 0})
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(error)
            with stack:
                output = Path(tmp) / "run"; result = self.run_fake(output)
                self.assertEqual(result["stopped"]["diagnostic"]["delivery"], "unknown")
                self.assertEqual(result["derived_conversation_judge_scores"], 0)
                with self.assertRaises(ValueError): self.run_fake(output)
                self.assertEqual(request.call_count, 1)

    def test_bad_judge_quote_keeps_minimax_answers_but_no_score(self):
        def handler(spec, key, packet, instruction):
            raw, latency = self.reply(spec, key, packet, instruction)
            if spec["kind"] == "judge":
                j = exp.scoring.base.parse_response(raw, spec["provider"])
                j["criterion_assessments"][0]["response_evidence"] = "Invented paraphrase"
                raw = self.encode(spec, j)
            return raw, latency
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(handler)
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(request.call_count, 3)
                self.assertEqual(result["valid_candidate_turns"], 2)
                self.assertEqual(result["complete_candidate_conversations"], 1)
                self.assertEqual(result["derived_conversation_judge_scores"], 0)

    def test_unclear_is_interval_not_forced_point_or_expected_candidate_label(self):
        def handler(spec, key, packet, instruction):
            raw, latency = self.reply(spec, key, packet, instruction)
            if spec["kind"] == "judge" and spec["stage"] == "initial":
                j = exp.scoring.base.parse_response(raw, spec["provider"])
                j["criterion_assessments"][0]["status"] = "unclear"; raw = self.encode(spec, j)
            return raw, latency
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(handler)
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(len(result["score_cells"]), 8)
                self.assertTrue(all(c["score"]["point_score"] is None for c in result["score_cells"]))

    def test_raw_saved_candidate_and_downstream_packet_hashes_are_bound(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"; self.run_fake(output)
                for filename, change in (
                    ("01.judgment.json", lambda r: r["result"].update(text="edited answer")),
                    ("03.attempt.json", lambda r: r.update(input_sha256="changed")),
                    ("03.judgment.json", lambda r: r.update(model_returned="other")),
                    ("01.response.json", lambda r: r["choices"][0]["message"].update(content="edited raw")),
                    ("complete.json", lambda r: r.update(judge_calls=15)),
                    ("external_call_acknowledgment.json", lambda r: r.update(maximum_calls=72)),
                ):
                    path = output / filename; original = path.read_text(); self.mutate(path, change)
                    with self.assertRaises(ValueError): exp.audit(ROOT, output)
                    path.write_text(original)
                (output / "01.judgment.json").rename(output / "25.judgment.json")
                with self.assertRaisesRegex(ValueError, "contiguous"): exp.audit(ROOT, output)

    def test_plan_never_reads_keys_or_calls_provider(self):
        with patch.object(exp, "read_setting") as keys, patch.object(exp, "request") as request:
            self.assertEqual(exp.plan(ROOT)["maximum_calls"], 24)
            keys.assert_not_called(); request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
