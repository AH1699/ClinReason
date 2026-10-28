from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import compact_feasibility_s65 as run

ROOT = Path(__file__).resolve().parents[1]


def portable_inputs():
    # Public controls stand in for private saved responses in portable unit tests.
    # The production source loader separately requires exact historical hashes.
    spec, catalog, rows = run.public_controls(ROOT)
    for i, row in enumerate(list(rows)):
        rows.append({**deepcopy(row), "id": "unit-test-source-" + str(i),
                     "kind": "source_probe", "expected_error": None})
    return spec, catalog, rows


class CompactPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = portable_inputs()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.core = run.Engine(ROOT, deepcopy(self.inputs), mode="offline_transport_fixture")

    def advance(self, until=16):
        while self.core.index < until and self.core.prepare() is not None:
            run.step(self.core, self.directory / str(self.core.index), run.next_fixture(self.core))

    def test_full_fake_transport_without_network_or_environment(self):
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), \
             patch("os.getenv", side_effect=AssertionError("No environment")):
            self.advance()
            self.assertIsNone(self.core.prepare())
        report = self.core.report()
        self.assertEqual((report["attempts"], report["accepted_judge_fixtures"], report["accepted_candidate_fixtures"]), (16, 12, 4))
        self.assertEqual(report["matching_fixture_repeat_vectors"], 6)
        self.assertEqual(report["fixture_unsafe_error_matches"], 2)
        self.assertFalse(report["live_acceptance_passed"])
        self.assertEqual(report["live_calls"], 0)
        self.assertFalse(report["paid_execution_ready"])

    def test_no_live_mode_or_duplicate_dispatch(self):
        with self.assertRaises(ValueError): run.Engine(ROOT, self.inputs, mode="live")
        self.core.prepare()
        with self.assertRaises(ValueError): self.core.prepare()
        self.assertTrue(self.core.report()["unsettled"])

    def test_judge_failure_preserved_closes_only_judge_lane(self):
        self.core.prepare(); raw = run.next_fixture(self.core)
        value = json.loads(raw["steps"][0]["content"][0]["text"])
        value["criterion_assessments"][0]["response_evidence_ref"]["first"] = "invalid"
        raw["steps"][0]["content"][0]["text"] = json.dumps(value)
        run.step(self.core, self.directory / "bad", raw)
        self.assertEqual(self.core.closed, {"judge"})
        self.assertGreater(self.core.monitored, 0)
        self.assertEqual(run.read(self.directory / "bad/0001.raw.bin"), raw)
        self.advance()
        report = self.core.report()
        self.assertEqual((report["attempts"], report["skipped"], report["accepted_candidate_fixtures"]), (5, 11, 4))

    def test_length_exhaustion_closes_only_one_candidate_model(self):
        self.advance(12); self.core.prepare()
        raw = run.next_fixture(self.core)
        raw["choices"][0]["finish_reason"] = "length"
        raw["choices"][0]["message"]["content"] = ""
        run.step(self.core, self.directory / "length", raw)
        self.assertEqual(self.core.closed, {"MiniMax-M3.1-Flash"})
        self.advance()
        self.assertEqual(self.core.report()["accepted_candidate_fixtures"], 2)
        self.assertEqual(self.core.report()["skipped"], 1)

    def test_missing_usage_stops_globally_no_unknown_as_zero(self):
        self.core.prepare(); raw = run.next_fixture(self.core); raw.pop("usage")
        run.step(self.core, self.directory / "unknown", raw)
        self.assertEqual(self.core.stop, "unknown_delivery_or_cost")
        self.assertEqual(self.core.unknown, 1)
        self.assertEqual(self.core.report()["unreached"], 15)
        self.assertIsNone(self.core.prepare())

    def test_pre_response_failure_is_unknown_and_not_retried(self):
        self.core.prepare()
        run.step(self.core, self.directory / "timeout", run.next_fixture(self.core), fault="connect_timeout")
        self.assertEqual(self.core.stop, "unknown_delivery_or_cost")
        self.assertEqual(len(self.core.accounts), 1)
        self.assertIsNone(self.core.prepare())

    def test_observed_input_scope_guard_is_not_byte_token_claim(self):
        self.core.prepare(); raw = run.next_fixture(self.core)
        raw["usage"]["total_input_tokens"] = 16001
        raw["usage"]["total_tokens"] = 16401
        run.step(self.core, self.directory / "scope", raw)
        self.assertEqual(self.core.stop, "unknown_delivery_or_cost")
        self.assertEqual(self.core.accounts[0]["reason"], "outside_verified_short_context_standard_price_scope")

    def test_simulated_spend_threshold_keeps_last_request(self):
        self.core.monitored = 3 * run.TICKS_PER_USD - 1
        self.core.prepare()
        run.step(self.core, self.directory / "threshold", run.next_fixture(self.core))
        self.assertEqual(self.core.stop, "simulated_spend_threshold_reached")
        self.assertGreater(self.core.monitored, 3 * run.TICKS_PER_USD)
        self.assertEqual(len(self.core.judgments), 1)
        self.assertIsNone(self.core.prepare())

    def test_candidate_caps_history_and_diagnostic_language_assignment(self):
        self.advance()
        for model, lang in (("MiniMax-M3.1-Flash", "en"), ("MiniMax-M3", "zh-Hans")):
            initial = self.core.contexts[model + "__initial"]["payload"]
            update = self.core.contexts[model + "__update"]["payload"]
            self.assertEqual(initial["max_completion_tokens"], 32768)
            self.assertNotIn("max_tokens", initial)
            self.assertEqual(initial["thinking"], {"type": "adaptive"})
            self.assertEqual(len(initial["messages"]), 2)
            self.assertEqual(len(update["messages"]), 4)
            self.assertEqual(update["messages"][2], {"role": "assistant", "content": self.core.answers[model + "__initial"]["text"]})
            self.assertNotIn("FIXTURE_REASONING", json.dumps(update))
            self.assertNotIn("criterion_anchors", json.dumps(update))
            self.assertEqual(initial["messages"][1]["content"], self.inputs[1]["HC-MT-REASON-027"]["family"]["variants"][lang]["turns"][0]["user"])
        self.assertNotIn("service_tier", self.core.contexts["MiniMax-M3.1-Flash__initial"]["payload"])

    def test_repeat_and_request_size_mutation_fail_closed(self):
        self.advance(6)
        self.core.contexts[self.core.rows[0]["id"]]["payload"]["store"] = True
        with self.assertRaises(ValueError): self.core.prepare()
        self.assertEqual(self.core.stop, "local_preparation_failure")
        core = run.Engine(ROOT, self.inputs, mode="offline_transport_fixture")
        core.plan["max_request_bytes"] = 1
        with self.assertRaises(ValueError): core.prepare()
        self.assertEqual(core.stop, "local_preparation_failure")

    def test_disagreement_is_retained_not_rewritten_as_agreement(self):
        self.advance()
        key = self.core.rows[6]["id"]
        self.core.judgments[key]["criterion_assessments"][0]["status"] = "partial"
        self.assertEqual(self.core.report()["matching_fixture_repeat_vectors"], 5)
        self.assertEqual(self.core.judgments[key]["criterion_assessments"][0]["status"], "partial")

    def test_source_loader_requires_exact_closed_journal(self):
        with patch.object(run.historical, "audit", return_value={"source_journal_sha256": "changed"}):
            with self.assertRaises(ValueError): run.source_inputs(ROOT, self.directory)

    def test_freeze_and_public_sanitized_result(self):
        self.assertEqual(run.snapshot(ROOT), run.read(ROOT / run.FREEZE))
        result = run.rehearse(ROOT, self.inputs)
        for forbidden in ("response_evidence", "rationale", "reasoning_content", "point_score", "api_key"):
            self.assertNotIn(forbidden, json.dumps(result))
        for row in result["request_sizes"]:
            self.assertLess(row["s65_input_characters"], row["s64_input_characters"])
            self.assertFalse(row["provider_tokens_measured"])
            self.assertLess(row["provider_request_utf8_bytes"], run.policy(ROOT)["max_request_bytes"])
