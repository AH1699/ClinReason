from copy import deepcopy
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from benchmark import run_guard_s37 as guard

ROOT = Path(__file__).resolve().parents[1]


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fixture"
        self.journal = guard.FixtureJournal(self.path, "a" * 64, 2, 100)
        self.payload = {"model": "fixture-model", "input": "synthetic"}
        self.reply = b'{"model":"fixture-model","status":"completed"}'

    def run_reply(self, reply=None, validator=None, amount=40, status=200):
        return self.journal.record("fixture-model", self.payload, amount,
            self.reply if reply is None else reply, validator or (lambda raw: {"valid": True}), status)

    def test_rounds_up_in_integer_micro_usd(self):
        self.assertEqual(guard.reserve_microusd(16000, 8192, "2", "6"), 81152)
        self.assertEqual(guard.reserve_microusd(1, 1, "0.1", "0.2"), 1)

    def test_invalid_bounds_and_prices_fail_closed(self):
        for tokens in (0, -1, True, 1.5, "10"):
            with self.assertRaises(guard.AdmissionBlocked): guard.reserve_microusd(tokens, 1, 1, 1)
        for rate in (float("nan"), "Infinity", -1, "not-a-price"):
            with self.assertRaises(guard.AdmissionBlocked): guard.reserve_microusd(1, 1, rate, 1)

    def test_current_checkpoint_cannot_dispatch(self):
        with self.assertRaises(guard.AdmissionBlocked): guard.require_live_ready(ROOT)
        with patch.object(guard, "load_json", return_value={"live_call_allowance": 999,
                "live_ready": True, "blocking_findings": []}):
            with self.assertRaises(guard.AdmissionBlocked): guard.require_live_ready(ROOT)

    def test_provider_specific_payload_limits_no_claim_shared_sampling(self):
        history = [{"role": "user", "content": "Fixture only"}]
        for provider in ("gemini", "grok", "minimax"):
            p = guard.candidate_payload(provider, "model", history, "instruction")
            self.assertNotIn("tools", p)
            if provider == "gemini": self.assertEqual(p["generation_config"]["max_output_tokens"], 8192)
            elif provider == "grok": self.assertEqual(p["max_output_tokens"], 8192)
            else:
                self.assertEqual(p["max_completion_tokens"], 8192)
                self.assertNotIn("temperature", p)
            if provider != "minimax": self.assertIs(p["store"], False)
        self.assertEqual(history, [{"role": "user", "content": "Fixture only"}])

    def test_bad_history_and_limits_are_rejected(self):
        for history in ([], [{"role": "assistant", "content": "x"}], [{"role": "user", "content": ""}]):
            with self.assertRaises(ValueError): guard.candidate_payload("grok", "x", history, "x")
        with self.assertRaises(ValueError):
            guard.candidate_payload("grok", "x", [{"role": "user", "content": "x"}], "x", True)

    def test_raw_and_attempt_exist_before_validator(self):
        def validate(raw):
            self.assertTrue((self.path / "0001.attempt.json").exists())
            self.assertTrue((self.path / "0001.payload.json").exists())
            self.assertEqual((self.path / "0001.raw.bin").read_bytes(), self.reply)
            return {"valid": True}
        self.assertTrue(self.run_reply(validator=validate)["accepted"])

    def test_malformed_json_bytes_retained_and_run_stops(self):
        bad = b'{"unterminated":\xff'
        self.assertFalse(self.run_reply(bad)["accepted"])
        self.assertEqual((self.path / "0001.raw.bin").read_bytes(), bad)
        self.assertEqual(self.journal.reserved, 40)
        with self.assertRaises(guard.AdmissionBlocked): self.run_reply()
        self.assertFalse((self.path / "0002.attempt.json").exists())

    def test_duplicate_and_nonfinite_json_rejected(self):
        for i, raw in enumerate((b'{"model":"fixture-model","model":"fixture-model"}',
                                 b'{"model":"fixture-model","number":NaN}')):
            journal = guard.FixtureJournal(Path(self.temp.name) / f"bad-{i}", "a"*64, 1, 100)
            result = journal.record("fixture-model", self.payload, 40, raw, lambda r: r)
            self.assertEqual(result["category"], "json_format")

    def test_http_error_raw_preserved_without_repair(self):
        result = self.run_reply(b"rate limited", status=429)
        self.assertEqual(result["category"], "http")
        self.assertFalse((self.path / "0001.accepted.json").exists())

    def test_exact_model_alias_rejected(self):
        result = self.run_reply(b'{"model":"fixture-model-latest"}')
        self.assertEqual(result["category"], "model_identity")

    def test_completion_and_format_rejection_retained(self):
        def reject(raw):
            raise ValueError("SECRET_EXCEPTION_TEXT")
        result = self.run_reply(validator=reject)
        self.assertEqual(result["category"], "response_validation")
        self.assertNotIn("SECRET_EXCEPTION_TEXT", (self.path / "0001.rejected.json").read_text())

    def test_unclear_semantic_judgment_is_accepted_not_retried(self):
        result = self.run_reply(validator=lambda raw: {"status": "unclear", "point_score": None})
        self.assertTrue(result["accepted"])
        self.assertFalse(self.journal.stopped)
        self.assertEqual(self.journal.attempts, 1)

    def test_unknown_delivery_keeps_full_reservation_and_no_exception_text(self):
        self.run_reply(TimeoutError("secret-key"))
        self.assertEqual(self.journal.reserved, 40)
        self.assertFalse((self.path / "0001.raw.bin").exists())
        self.assertNotIn("secret-key", (self.path / "0001.rejected.json").read_text())

    def test_keyboard_interrupt_is_terminal_and_reraised(self):
        with self.assertRaises(KeyboardInterrupt): self.run_reply(KeyboardInterrupt())
        self.assertTrue((self.path / "0001.attempt.json").exists())
        self.assertTrue(self.journal.stopped)
        with self.assertRaises(guard.AdmissionBlocked): self.run_reply()

    def test_budget_is_reserved_before_next_attempt_and_never_refunded(self):
        self.run_reply(amount=60)
        with self.assertRaises(guard.AdmissionBlocked): self.run_reply(amount=41)
        self.assertEqual(self.journal.reserved, 60)
        self.assertFalse((self.path / "0002.attempt.json").exists())

    def test_exact_budget_and_attempt_boundary(self):
        self.run_reply(amount=50); self.run_reply(amount=50)
        self.assertEqual(self.journal.reserved, 100)
        with self.assertRaises(guard.AdmissionBlocked): self.run_reply(amount=1)
        self.assertFalse((self.path / "0003.attempt.json").exists())

    def test_no_resume_or_overwrite_and_private_modes(self):
        self.run_reply()
        with self.assertRaises(FileExistsError): guard.FixtureJournal(self.path, "b"*64, 2, 100)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o700)
        for path in self.path.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_pre_dispatch_disk_error_is_terminal(self):
        with patch.object(guard, "_write_exclusive", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): self.run_reply()
        self.assertTrue(self.journal.stopped)
        self.assertFalse((self.path / "0001.raw.bin").exists())

    def test_transport_callable_cannot_be_used_as_fixture(self):
        with self.assertRaises(ValueError): self.run_reply(lambda: self.reply)
        self.assertEqual(self.journal.attempts, 0)


if __name__ == "__main__":
    unittest.main()
