import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import boundary_s30 as exp
from benchmark.provenance import sha256_json
from benchmark.providers.observed_http import DiagnosticRequestError

ROOT = Path(__file__).resolve().parents[1]


class S30BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.policy, self.packets, self.expected, self.repeats = exp.inputs(ROOT)
        self.approved = sha256_json(exp.check_manifest(ROOT))

    def reply(self, provider, model, key, packet, instruction, timeout):
        self.assertEqual(timeout, 240)
        packet_key = next(k for k, p in self.packets.items() if p == packet)
        statuses = self.expected[packet_key] or ["unclear", "unclear"]
        judgment = {"criterion_assessments": [
            {"requirement_index": i, "status": status,
             "response_evidence": packet["transcript"][3]["content"] if status in ("met", "partial") else "",
             "rationale": "Synthetic unit-test response, not clinical evidence."}
            for i, status in zip((1, 3), statuses)]}
        raw = {"status": "completed", "model": model}
        if provider == "gemini":
            raw["steps"] = [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(judgment)}]}]
        else:
            raw["output"] = [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(judgment)}]}]
        return raw, 1

    def mocks(self, handler=None):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(exp, "read_setting", return_value="unit-test-only-key"))
        request = stack.enter_context(patch.object(exp, "request", side_effect=handler or self.reply))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        return stack, request

    def run_fake(self, output):
        return exp.run(ROOT, output, ROOT / "not-read", 24, self.approved)

    def change_json(self, path, change):
        obj = json.loads(path.read_text())
        change(obj)
        path.write_text(json.dumps(obj))

    def test_frozen_scope_and_blinded_schedule(self):
        plan = exp.schedule(self.policy, self.packets, self.repeats)
        self.assertEqual(len(plan), 24)
        self.assertEqual(sum(p[0] == "repeat" for p in plan), 4)
        self.assertEqual(sum(v is not None for v in self.expected.values()), 8)
        for packet in self.packets.values():
            self.assertEqual(set(packet), {"case_id", "case_content_hash", "language", "transcript",
                                           "target_requirements", "level_definitions"})
        self.assertEqual({key for phase, key, _ in plan if phase == "repeat"}, self.repeats)
        self.assertEqual([p[2]["provider"] for p in plan[:2]], ["gemini", "grok"])

    def test_exact_two_criteria_order_and_literal_update_evidence(self):
        packet = self.packets["observed_partial__en"]
        raw, _ = self.reply("gemini", "gemini-3.8-flash", "unused", packet, "test", 240)
        good = exp.base.parse_response(raw, "gemini")
        exp.validate(good, packet)
        for mutate in (
            lambda j: j["criterion_assessments"].reverse(),
            lambda j: j["criterion_assessments"].pop(),
            lambda j: j.update(score=80),
            lambda j: j["criterion_assessments"][0].update(response_evidence=""),
            lambda j: j["criterion_assessments"][0].update(response_evidence=packet["transcript"][1]["content"]),
            lambda j: j["criterion_assessments"][0].update(requirement_index=True),
            lambda j: j["criterion_assessments"][0].update(status="invented"),
        ):
            altered = deepcopy(good)
            mutate(altered)
            with self.assertRaises(ValueError):
                exp.validate(altered, packet)

    def test_provider_payload_uses_no_retries_and_hides_author_keys(self):
        for spec in exp.JUDGES:
            with patch.object(exp, "post_json_observed", return_value=({}, 1)) as http:
                exp.request(spec["provider"], spec["model"], "synthetic-secret",
                            self.packets["complete__en"], "test instruction", 240)
                args, kwargs = http.call_args
                payload = args[1]
                self.assertFalse(payload["store"])
                self.assertEqual(kwargs["retries"], 0)
                self.assertEqual(kwargs["timeout"], 240)
                self.assertNotIn("synthetic-secret", json.dumps(payload))
                for forbidden in ("expected_statuses", "complete__en", "author_expected"):
                    self.assertNotIn(forbidden, json.dumps(payload))
                for setting in ("temperature", "top_p", "seed"):
                    self.assertNotIn(setting, payload)

    def test_acknowledgment_cap_and_output_checks_precede_keys_or_calls(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp, \
                patch.object(exp, "read_setting") as keys, patch.object(exp, "request") as request:
            output = Path(tmp) / "run"
            for cap, approval in ((24, None), (24, "wrong"), (25, self.approved), (0, self.approved)):
                with self.assertRaisesRegex(ValueError, "approved protocol"):
                    exp.run(ROOT, output, ROOT / "not-read", cap, approval)
            with self.assertRaises(ValueError):
                exp.run(ROOT, ROOT / "out-of-scope-s30", ROOT / "not-read", 24, self.approved)
            keys.assert_not_called()
            request.assert_not_called()
            self.assertFalse(output.exists())

    def test_complete_mock_gate_and_no_repeat_authority(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks()
            with stack:
                output = Path(tmp) / "run"
                result = self.run_fake(output)
                self.assertEqual(request.call_count, 24)
                self.assertEqual((result["known_first_criterion_matches"], result["known_first_criterion_count"]), (32, 32))
                self.assertEqual((result["repeat_criterion_matches"], result["repeat_criterion_count"]), (8, 8))
                self.assertEqual(result["exploratory_first_judgments"], 4)
                self.assertTrue(result["ready_to_design_full_scoring_repeat"])
                self.assertFalse(result["calibration_complete"])
                self.assertFalse(result["candidate_pilot_authorized"])
                self.assertEqual(result, exp.audit(ROOT, output))
                with self.assertRaisesRegex(ValueError, "fresh"):
                    self.run_fake(output)
                self.assertEqual(request.call_count, 24)

    def test_known_mismatch_is_retained_and_not_early_stopped(self):
        def mismatch(*args):
            raw, latency = self.reply(*args)
            if args[0] == "gemini" and args[3] == self.packets["complete__en"]:
                value = exp.base.parse_response(raw, "gemini")
                value["criterion_assessments"][0]["status"] = "partial"
                raw["steps"][0]["content"][0]["text"] = json.dumps(value)
            return raw, latency
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(mismatch)
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(request.call_count, 24)
                self.assertEqual(result["known_first_criterion_matches"], 31)
                self.assertFalse(result["ready_to_design_full_scoring_repeat"])

    def test_repeat_flip_fails_even_when_first_hypotheses_all_match(self):
        calls = 0
        def flipped(*args):
            nonlocal calls
            calls += 1
            raw, latency = self.reply(*args)
            if calls == 21:
                value = exp.base.parse_response(raw, args[0])
                value["criterion_assessments"][0]["status"] = "partial"
                raw["steps"][0]["content"][0]["text"] = json.dumps(value)
            return raw, latency
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks(flipped)
            with stack:
                result = self.run_fake(Path(tmp) / "run")
                self.assertEqual(result["known_first_criterion_matches"], 32)
                self.assertEqual(result["repeat_criterion_matches"], 7)
                self.assertFalse(result["ready_to_design_full_scoring_repeat"])

    def test_timeout_stops_with_secret_safe_diagnostic_and_no_resume(self):
        diagnostic = {"version": "transport-diagnostic-v1", "category": "timeout", "http_status": None,
                      "elapsed_ms": 240001, "delivery": "unknown", "attempts": 1, "automatic_retries": 0}
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, request = self.mocks(DiagnosticRequestError(diagnostic))
            with stack:
                output = Path(tmp) / "run"
                result = self.run_fake(output)
                self.assertEqual((result["attempted_calls"], result["valid_judgments"]), (1, 0))
                self.assertEqual(result["stopped"]["diagnostic"], diagnostic)
                self.assertFalse(result["ready_to_design_full_scoring_repeat"])
                with self.assertRaises(ValueError):
                    self.run_fake(output)
                self.assertEqual(request.call_count, 1)
                self.change_json(output / "stopped.json", lambda j: j.update(body="not-allowed"))
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    exp.audit(ROOT, output)

    def test_model_drift_and_invalid_json_retain_raw_and_stop(self):
        for failure in ("model", "json", "nonobject"):
            def invalid(*args):
                raw, latency = self.reply(*args)
                if failure == "model":
                    raw["model"] = "unrequested-alias"
                elif failure == "json":
                    raw["steps"][0]["content"][0]["text"] = "not-json"
                else:
                    raw = []
                return raw, latency
            with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
                stack, request = self.mocks(invalid)
                with stack:
                    output = Path(tmp) / "run"
                    result = self.run_fake(output)
                    self.assertEqual(request.call_count, 1)
                    self.assertEqual(result["stopped"]["kind"], "response_validation_failure")
                    self.assertTrue((output / "01.response.json").exists())
                    self.assertFalse(result["ready_to_design_full_scoring_repeat"])

    def test_tampered_raw_binding_and_orphan_artifacts_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"
                self.run_fake(output)
                saved = (output / "01.judgment.json").read_text()
                self.change_json(output / "01.judgment.json", lambda j: j["judgment"]["criterion_assessments"][0].update(rationale="edited"))
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    exp.audit(ROOT, output)
                (output / "01.judgment.json").write_text(saved)
                (output / "25.response.json").write_text("{}")
                with self.assertRaisesRegex(ValueError, "counts"):
                    exp.audit(ROOT, output)

    def test_interruption_cannot_masquerade_as_completion(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"
                self.run_fake(output)
                (output / "complete.json").unlink()
                result = exp.audit(ROOT, output)
                self.assertEqual(result["status"], "incomplete_saved_prefix")
                self.assertFalse(result["ready_to_design_full_scoring_repeat"])

    def test_missing_prefix_and_acknowledgment_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "work") as tmp:
            stack, _ = self.mocks()
            with stack:
                output = Path(tmp) / "run"
                self.run_fake(output)
                ack = output / "external_call_acknowledgment.json"
                old = ack.read_text()
                self.change_json(ack, lambda j: j.update(maximum_calls=25))
                with self.assertRaisesRegex(ValueError, "acknowledgment"):
                    exp.audit(ROOT, output)
                ack.write_text(old)
                (output / "01.attempt.json").rename(output / "00.attempt.json")
                with self.assertRaisesRegex(ValueError, "prefix"):
                    exp.audit(ROOT, output)


if __name__ == "__main__":
    unittest.main()
