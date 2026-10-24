from copy import deepcopy
from http.client import IncompleteRead
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from benchmark import transport_s39 as transport, workflow_s38 as workflow
from benchmark.config import load_json
from tests.test_usage_s39 import usage_fixture
from tests.test_workflow_s38 import envelope, reply_fixture

ROOT = Path(__file__).resolve().parents[1]


class Response:
    def __init__(self, body=b"", status=200, headers=None, chunks=None):
        self.body, self.status, self.headers, self.chunks = body, status, headers or {}, chunks
        self.closed = False

    def getheader(self, name):
        return self.headers.get(name)

    def read(self, size):
        if self.chunks is not None:
            chunk = self.chunks.pop(0) if self.chunks else b""
            if isinstance(chunk, BaseException): raise chunk
            return chunk
        value, self.body = self.body[:size], self.body[size:]
        return value

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, response):
        self.response, self.calls, self.closed = response, [], False

    def request(self, method, path, body, headers):
        self.calls.append((method, path, body, headers))

    def getresponse(self):
        if isinstance(self.response, BaseException): raise self.response
        return self.response

    def close(self):
        self.closed = True


def candidate(provider="grok", model="grok-4.7", text="Synthetic answer"):
    row = {"provider": provider, "model": model}
    raw = json.loads(envelope(row, text)); raw["usage"] = usage_fixture(provider)
    return json.dumps(raw).encode()


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)/"capture"
        self.journal = transport.CaptureJournal(ROOT, self.directory, 2)
        self.payload = {"model": "grok-4.7", "input": "Synthetic prompt", "store": False}

    def send(self, response=None, validator=None):
        connection = Connection(response if response is not None else Response(candidate()))
        self.connection = connection
        validator = validator or (lambda raw: workflow.decode_candidate(raw, "grok", "grok-4.7"))
        return self.journal.exchange("grok", self.payload, validator, connection_factory=lambda *a, **k: connection)

    def test_success_raw_exact_and_private_permissions(self):
        body = candidate()
        result = self.send(Response(body))
        self.assertTrue(result["accepted"])
        self.assertEqual((self.directory/"0001.raw.bin").read_bytes(), body)
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in self.directory.iterdir()))
        self.assertTrue(self.connection.closed)

    def test_attempt_and_payload_durable_before_connection(self):
        def factory(host, timeout):
            self.assertEqual(host, "api.x.ai")
            self.assertEqual(timeout, 240)
            self.assertTrue((self.directory/"0001.attempt.json").exists())
            self.assertEqual(load_json(self.directory/"0001.payload.json"), self.payload)
            return Connection(Response(candidate()))
        result = self.journal.exchange("grok", self.payload, lambda raw: {}, connection_factory=factory)
        self.assertTrue(result["accepted"])

    def test_raw_saved_before_validator_and_no_auth_headers_logged(self):
        def validate(raw):
            self.assertTrue((self.directory/"0001.raw.bin").exists())
            return {}
        self.send(Response(candidate(), headers={"Set-Cookie": "secret", "Location": "https://evil.example/"}), validate)
        for path in self.directory.iterdir():
            self.assertNotIn(transport.FIXTURE_KEY, path.read_text())
            self.assertNotIn("evil.example", path.read_text())
            self.assertNotIn("Set-Cookie", path.read_text())
        self.assertEqual(self.connection.calls[0][0:2], ("POST", "/v1/responses"))

    def test_production_entry_always_disabled(self):
        with self.assertRaises(transport.guard.AdmissionBlocked):
            transport.run_live(approved=True, max_calls=816, budget=55)

    def test_unknown_endpoint_model_and_tools_rejected_before_dispatch(self):
        for provider, payload in (("other", self.payload), ("grok", {"model": "alias"}),
                                  ("grok", {**self.payload, "tools": []})):
            with self.assertRaises(ValueError):
                self.journal.exchange(provider, payload, lambda raw: {}, connection_factory=lambda *a, **k: self.fail())
        self.assertEqual(self.journal.index, 0)

    def test_http_errors_and_redirect_not_retried(self):
        for status in (302, 429, 500):
            journal = transport.CaptureJournal(ROOT, Path(self.temp.name)/str(status), 2)
            connection = Connection(Response(b"upstream error", status))
            result = journal.exchange("grok", self.payload, lambda raw: self.fail(), connection_factory=lambda *a, **k: connection)
            self.assertEqual(result["category"], "http_status")
            self.assertEqual(len(connection.calls), 1)
            self.assertEqual((journal.directory/"0001.raw.bin").read_bytes(), b"upstream error")
            self.assertEqual(result["accounting"]["status"], "unknown")

    def test_invalid_json_and_nonfinite_duplicate_and_utf8_retained(self):
        for i, body in enumerate((b"not json", b'{"a":1,"a":2}', b'{"a":NaN}', b"\xff")):
            journal = transport.CaptureJournal(ROOT, Path(self.temp.name)/str(i), 1)
            result = journal.exchange("grok", self.payload, lambda raw: self.fail(),
                connection_factory=lambda *a, **k: Connection(Response(body)))
            self.assertEqual(result["category"], "json_format")
            self.assertEqual((journal.directory/"0001.raw.bin").read_bytes(), body)

    def test_partial_body_before_timeout_retained(self):
        result = self.send(Response(chunks=[b"prefix", TimeoutError("do-not-log-secret")]))
        self.assertFalse(result["accepted"])
        self.assertEqual((self.directory/"0001.raw.bin").read_bytes(), b"prefix")
        self.assertFalse(load_json(self.directory/"0001.capture.json")["body_eof"])
        self.assertTrue(self.connection.closed)
        self.assertNotIn("do-not-log-secret", (self.directory/"0001.rejected.json").read_text())

    def test_incomplete_read_partial_bytes_retained(self):
        result = self.send(Response(chunks=[b"a", IncompleteRead(b"bc", 5)]))
        self.assertEqual(result["category"], "incomplete_body")
        self.assertEqual((self.directory/"0001.raw.bin").read_bytes(), b"abc")

    def test_size_limit_retains_bounded_prefix_and_stops(self):
        self.journal.policy["max_response_bytes"] = 8
        result = self.send(Response(b"0123456789"))
        self.assertEqual(result["category"], "response_size_limit")
        self.assertEqual((self.directory/"0001.raw.bin").read_bytes(), b"012345678")

    def test_content_length_mismatch_retains_body(self):
        result = self.send(Response(candidate(), headers={"Content-Length": "999999"}))
        self.assertEqual(result["category"], "content_length_mismatch")

    def test_unsupported_encoding_stops_without_decompressing(self):
        self.assertEqual(self.send(Response(b"compressed", headers={"Content-Encoding": "gzip"}))["category"],
                         "unsupported_content_encoding")

    def test_response_deadline_stops_without_retry(self):
        self.journal.policy["exchange_deadline_seconds"] = 1
        with patch.object(transport.time, "monotonic", side_effect=[0, 2, 3]):
            result = self.send()
        self.assertEqual(result["category"], "response_deadline")

    def test_interrupt_records_unknown_charge_and_is_reraised(self):
        with self.assertRaises(KeyboardInterrupt):
            self.send(Response(chunks=[b"prefix", KeyboardInterrupt()]))
        self.assertTrue(self.journal.stopped)
        self.assertEqual(load_json(self.directory/"0001.accounting.json")["status"], "unknown")
        self.assertEqual(load_json(self.directory/"0001.capture.json")["category"], "interrupted")
        self.assertTrue(self.connection.closed)

    def test_failure_forbids_retry_and_directory_reuse(self):
        self.send(Response(b"bad"))
        with self.assertRaises(transport.guard.AdmissionBlocked): self.send()
        with self.assertRaises(FileExistsError): transport.CaptureJournal(ROOT, self.directory, 1)

    def test_attempt_limit(self):
        self.send(); self.send()
        with self.assertRaises(transport.guard.AdmissionBlocked): self.send()
        self.assertEqual(self.journal.index, 2)

    def test_write_failure_before_dispatch(self):
        with patch.object(transport.guard, "_write_exclusive", side_effect=OSError("secret")):
            with self.assertRaises(OSError):
                self.journal.exchange("grok", self.payload, lambda raw: {}, connection_factory=lambda *a, **k: self.fail())
        self.assertTrue(self.journal.stopped)

    def test_metadata_disk_failure_stops_and_closes_connection(self):
        original = transport.guard._write_exclusive
        def write(path, raw):
            if path.name.endswith(".accounting.json"):
                raise OSError("simulated disk full")
            return original(path, raw)
        with patch.object(transport.guard, "_write_exclusive", side_effect=write):
            with self.assertRaises(OSError): self.send()
        self.assertTrue(self.connection.closed)
        self.assertTrue(self.journal.stopped)
        with self.assertRaises(transport.guard.AdmissionBlocked): self.send()

    def test_connection_failure_is_unknown_cost_not_zero(self):
        result = self.send(TimeoutError("private error message"))
        self.assertEqual(result["accounting"]["status"], "unknown")
        self.assertIsNone(result["accounting"]["provider_billed_usd_ticks"])
        self.assertEqual(load_json(self.directory/"0001.capture.json")["delivery"], "unknown")
        self.assertFalse((self.directory/"0001.raw.bin").exists())
        self.assertTrue(self.connection.closed)

    def test_wrong_model_cost_not_guessed_from_requested_price(self):
        result = self.send(Response(candidate(model="other")))
        self.assertEqual(result["category"], "model_identity")
        self.assertEqual(result["accounting"]["status"], "unknown")

    def test_invalid_answer_still_retains_valid_billing(self):
        result = self.send(Response(candidate(text="")))
        self.assertEqual(result["category"], "response_validation")
        self.assertEqual(result["accounting"]["provider_billed_usd_ticks"], 37756001)

    def test_missing_usage_stops_before_answer_scoring(self):
        raw = json.loads(candidate()); del raw["usage"]
        result = self.send(Response(json.dumps(raw).encode()), lambda raw: self.fail())
        self.assertEqual(result["category"], "usage_accounting")

    def test_oversized_request_rejected_before_connection(self):
        self.journal.policy["max_request_bytes"] = 1
        with self.assertRaises(ValueError): self.send()
        self.assertEqual(self.journal.index, 0)

    def test_all_six_models_use_fixed_endpoint_and_visible_answer(self):
        plan = workflow.design(ROOT)
        for i, spec in enumerate(plan["candidates"]):
            journal = transport.CaptureJournal(ROOT, Path(self.temp.name)/f"model-{i}", 1)
            connection = Connection(Response(candidate(spec["provider"], spec["model"])))
            def factory(host, timeout):
                self.assertEqual(host, transport.ENDPOINTS[spec["provider"]][0]); return connection
            result = journal.exchange(spec["provider"], {"model": spec["model"]},
                lambda raw: workflow.decode_candidate(raw, spec["provider"], spec["model"]), connection_factory=factory)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["result"], {"text": "Synthetic answer"})

    def run_integrated(self, phase, recheck, count):
        session = workflow.OfflineSession(ROOT, Path(self.temp.name)/"workflow", phase, recheck)
        capture = transport.CaptureJournal(ROOT, Path(self.temp.name)/"integrated", count)
        while (payload := session.next_request()) is not None:
            row = session.pending
            raw = json.loads(reply_fixture(session)); raw["usage"] = usage_fixture(row["provider"])
            body = json.dumps(raw).encode()
            context = session.contexts[row["sequence"]]
            def validate(raw):
                if row["kind"] == "candidate":
                    return workflow.decode_candidate(raw, row["provider"], row["model"])
                return workflow.score.decode(raw, row["provider"], row["model"], context["packet"])
            result = capture.exchange(row["provider"], payload, validate,
                connection_factory=lambda *a, **k: Connection(Response(body)))
            self.assertTrue(result["accepted"])
            self.assertTrue(session.accept_reply(body)["accepted"])
        self.assertTrue(session.report()["complete"])
        self.assertEqual(capture.index, count)
        self.assertEqual(transport.usage.summarize(capture.accounts)["unknown_charge_attempts"], 0)
        return session

    def test_s38_full_first_workflow_with_capture_and_usage(self):
        session = self.run_integrated("first", False, 816)
        self.assertEqual(session.report()["first_conversation_judge_records"], 216)

    def test_s38_confirmation_with_control_recheck_capture_and_usage(self):
        session = self.run_integrated("confirmation", True, 504)
        self.assertEqual(session.report()["first_conversation_judge_records"], 144)
        self.assertEqual(session.report()["repeat_conversation_judge_records"], 0)
        self.assertTrue(session.report()["control_gate"]["pass"])

    def test_frozen_snapshot_and_public_audit(self):
        self.assertEqual(transport.snapshot(ROOT), load_json(ROOT/transport.FREEZE))
        self.assertEqual(transport.audit(ROOT), load_json(ROOT/"data/audit/s39_capture_summary.json"))


if __name__ == "__main__":
    unittest.main()
