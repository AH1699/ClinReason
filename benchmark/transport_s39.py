"""Durable HTTP exchange with injected connections; production entry disabled.

No environment/key loading, retries, redirects, proxy discovery or live connector
is provided. Tests inject HTTPConnection-shaped fakes, using a fixed dummy key.
Frozen S26–S38 runners are not modified by this new component.
"""

from copy import deepcopy
import hashlib
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import threading
import time

from . import run_guard_s37 as guard, usage_s39 as usage, workflow_s38 as workflow
from .config import load_json
from .provenance import sha256_json

POLICY = "config/transport_s39_v1.json"
FREEZE = "config/transport_s39_frozen_v1.json"
ENDPOINTS = {
    "gemini": ("generativelanguage.googleapis.com", "/v1beta/interactions", "x-goog-api-key"),
    "grok": ("api.x.ai", "/v1/responses", "Authorization"),
    "minimax": ("api.minimax.io", "/v1/chat/completions", "Authorization"),
}
FIXTURE_KEY = "S39-OFFLINE-FIXTURE-NOT-A-CREDENTIAL"


def run_live(*args, **kwargs):
    # Not overridable by a JSON flag or a supplied approval string in this release.
    raise guard.AdmissionBlocked("S39 live dispatch disabled: spending policy and approval protocol unfinished")


def strict_json(body):
    def reject(value):
        raise ValueError("Nonfinite JSON")
    return json.loads(body.decode("utf-8"), object_pairs_hook=guard._strict_object, parse_constant=reject)


class CaptureFailure(Exception):
    def __init__(self, category):
        self.category = category
        super().__init__(category)


class CaptureJournal:
    """Fresh-directory serial capture; injection-only, no resume or live credentials.

    A durable attempt and request body precede the connection factory. Body chunks
    are saved before parsing. Unknown delivery/cost remains unknown after failure.
    """
    def __init__(self, root, directory, max_attempts):
        self.root = root
        self.policy = load_json(root / POLICY)
        self.maximum = guard.positive_integer(max_attempts)
        if self.maximum > 1320:
            raise ValueError("Attempt allowance exceeds experiment design")
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        self.index, self.stopped = 0, False
        self.accounts = []
        self.lock = threading.Lock()
        plan = workflow.design(root)
        self.specs = {(s["provider"], s["model"]): s for s in [*plan["candidates"], *plan["judges"]]}
        self.protocol = sha256_json(snapshot(root))
        guard._write_exclusive(self.directory / "run.json", guard._json_bytes({
            "mode": "injected_http_fixture_only", "live_calls": 0, "automatic_retries": 0,
            "max_attempts": self.maximum, "protocol_sha256": self.protocol, "resume_allowed": False,
            "costs_are_simulated": True, "spending_authorized": False}))

    def exchange(self, provider, payload, validator, *, connection_factory):
        with self.lock:
            return self._exchange(provider, payload, validator, connection_factory)

    def _exchange(self, provider, payload, validator, connection_factory):
        if self.stopped or self.index >= self.maximum:
            raise guard.AdmissionBlocked("Stopped or attempt allowance exhausted; no retry")
        if not isinstance(payload, dict) or (provider, payload.get("model")) not in self.specs:
            raise ValueError("Unknown provider/model")
        if any(k in payload for k in ("tools", "previous_response_id", "previous_interaction_id", "stream", "background")):
            raise ValueError("Only stateless, nonstreaming, tool-free fixture requests")
        body = guard._json_bytes(payload)
        if len(body) > self.policy["max_request_bytes"]:
            raise ValueError("Request exceeds byte limit")
        spec = self.specs[provider, payload["model"]]
        host, path, auth = ENDPOINTS[provider]
        self.index += 1
        self.stopped = True  # Crash or write failure must not permit another request.
        stem = f"{self.index:04d}"
        def write(suffix, value):
            guard._write_exclusive(self.directory / (stem + suffix), guard._json_bytes(value))
        write(".attempt.json", {"sequence": self.index, "provider": provider, "model": spec["model"],
            "protocol_sha256": self.protocol, "payload_sha256": hashlib.sha256(body).hexdigest(),
            "delivery": "reserved_before_connection", "prospective_cost_bound": None,
            "automatic_retries": 0, "fixture_only": True})
        guard._write_exclusive(self.directory / (stem + ".payload.json"), body)
        headers = {"Content-Type": "application/json", "Accept-Encoding": "identity",
                   auth: FIXTURE_KEY if provider == "gemini" else "Bearer " + FIXTURE_KEY}
        response = connection = None
        status = None
        received = 0
        digest = hashlib.sha256()
        eof = False
        category = "transport_or_interruption"
        accounting = usage.account(None, spec)
        started = time.monotonic()
        accepted = None
        try:
            # The callback is an explicit test seam, never a default network client.
            connection = connection_factory(host, timeout=self.policy["socket_timeout_seconds"])
            connection.request("POST", path, body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            if type(status) is not int or not 100 <= status <= 599:
                raise CaptureFailure("invalid_http_status")
            length = response.getheader("Content-Length")
            encoding = response.getheader("Content-Encoding")
            limit = self.policy["max_response_bytes"]
            raw_path = self.directory / (stem + ".raw.bin")
            fd = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as raw_file:
                guard._sync_dir(self.directory)
                while True:
                    if time.monotonic() - started >= self.policy["exchange_deadline_seconds"]:
                        raise CaptureFailure("response_deadline")
                    interrupted = False
                    try:
                        chunk = response.read(min(65536, limit + 1 - received))
                    except IncompleteRead as exc:
                        chunk, interrupted = exc.partial, True
                    if not isinstance(chunk, bytes):
                        raise CaptureFailure("invalid_body_chunk")
                    if len(chunk) > limit + 1 - received:
                        chunk, interrupted = chunk[:limit + 1 - received], True
                    if chunk:
                        raw_file.write(chunk)
                        raw_file.flush()
                        os.fsync(raw_file.fileno())
                        digest.update(chunk)
                        received += len(chunk)
                    if received > limit:
                        raise CaptureFailure("response_size_limit")
                    if interrupted:
                        raise CaptureFailure("incomplete_body")
                    if not chunk:
                        eof = True
                        break
            if length is not None and (not length.isascii() or not length.isdecimal() or int(length) != received):
                raise CaptureFailure("content_length_mismatch")
            if encoding not in (None, "identity"):
                raise CaptureFailure("unsupported_content_encoding")
            if not 200 <= status < 300:
                raise CaptureFailure("http_status")
            category = "json_format"
            raw = strict_json(raw_path.read_bytes())
            accounting = usage.account(raw, spec)  # Keep cost even if later answer validation fails.
            category = "model_identity"
            if not isinstance(raw, dict) or raw.get("model") != spec["model"]:
                raise ValueError("Exact requested model required")
            category = "usage_accounting"
            if accounting["status"] == "unknown":
                raise usage.UsageError("Cannot reconcile request usage")
            category = "response_validation"
            accepted = validator(raw)
            write(".accepted.json", {"result": accepted, "raw_sha256": digest.hexdigest()})
            category = "accepted"
        except BaseException as exc:
            if isinstance(exc, CaptureFailure):
                category = exc.category
            elif isinstance(exc, (KeyboardInterrupt, SystemExit)):
                category = "interrupted"
            write(".rejected.json", {"category": category, "exception_text_retained": False,
                "charge_may_have_occurred": True, "retry": False})
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
        finally:
            # No returned headers, URLs, key values or exception messages in metadata.
            try:
                write(".capture.json", {"status": status, "bytes_saved": received, "body_eof": eof,
                    "body_sha256": digest.hexdigest() if response is not None else None,
                    "category": category, "elapsed_ms": max(0, round((time.monotonic()-started)*1000)),
                    "delivery": "response_received" if response is not None else "unknown",
                    "live_calls": 0, "fixture_only": True})
                write(".accounting.json", accounting)
                self.accounts.append(accounting)
            finally:
                # Close even after a disk failure. No retry or state rollback.
                for resource in (response, connection):
                    if resource is not None:
                        try:
                            resource.close()
                        except Exception:
                            pass
        self.stopped = category != "accepted"
        return {"accepted": not self.stopped, "category": category, "result": accepted,
                "accounting": deepcopy(accounting)}


def snapshot(root):
    paths = [POLICY, workflow.FREEZE, workflow.ROSTER, "benchmark/transport_s39.py",
             "benchmark/usage_s39.py", "tests/test_transport_s39.py", "tests/test_usage_s39.py"]
    return {"version": "s39-capture-accounting-v1", "live_call_allowance": 0,
        "sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}


def audit(root):
    workflow.audit(root)
    if snapshot(root) != load_json(root / FREEZE):
        raise ValueError("S39 capture snapshot changed")
    return {"version": "s39-capture-accounting-v1", "live_ready": False, "live_calls": 0,
        "new_cases": 0, "new_model_scores": 0, "http_capture": "injected_connections_tested",
        "provider_usage": "gemini_thoughts_minimax_completion_grok_billed_ticks",
        "budget_guarantee": False, "production_entry": "unconditionally_disabled",
        "snapshot_sha256": sha256_json(snapshot(root))}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), indent=2))
