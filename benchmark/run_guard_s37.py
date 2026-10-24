"""Offline admission/retention primitives; deliberately NO network or key loading.

FixtureJournal tests the future runner's write-before-send contract with supplied
bytes/errors. It is not a live dispatcher, and estimates cannot authorize one.
"""

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import threading

from .config import load_json
from .provenance import sha256_json

READINESS = "config/run_s37_readiness_v1.json"


class AdmissionBlocked(ValueError):
    pass


def positive_integer(value):
    if type(value) is not int or value <= 0:
        raise AdmissionBlocked("Expected a positive integer bound")
    return value


def reserve_microusd(input_tokens, all_billed_output_tokens, input_rate, output_rate):
    """Arithmetic only. Caller MUST establish bounds/rates; this proves neither.

    Rates are USD per million tokens; multiplying tokens by these rates gives
    micro-USD. Round UP, reserve the full amount, never reclaim from a bad reply.
    """
    positive_integer(input_tokens); positive_integer(all_billed_output_tokens)
    try:
        rates = [Decimal(str(r)) for r in (input_rate, output_rate)]
        if any(not r.is_finite() or r < 0 for r in rates):
            raise AdmissionBlocked("Invalid price")
        return int((input_tokens * rates[0] + all_billed_output_tokens * rates[1])
                   .to_integral_value(rounding=ROUND_CEILING))
    except (InvalidOperation, TypeError):
        raise AdmissionBlocked("Invalid price") from None


def readiness(root):
    record = load_json(root / READINESS)
    # This release intentionally cannot become live-ready by flipping JSON flags.
    return {"live_ready": False, "live_call_allowance": 0,
        "record_sha256": sha256_json(record),
        "blockers": ["S37 is an offline checkpoint; no live dispatcher or approval fingerprint",
                     *record["blocking_findings"]]}


def require_live_ready(root):
    state = readiness(root)
    if not state["live_ready"]:
        raise AdmissionBlocked("Live dispatch disabled: unverified billed-token bounds, protocol and approval")


def candidate_payload(provider, model, history, instruction, output_limit=8192):
    """Draft provider limits, NOT a claim they bound all billable tokens equally."""
    positive_integer(output_limit)
    if (not isinstance(model, str) or not model.strip() or not instruction.strip() or not history
            or any(set(t) != {"role", "content"} or t["role"] != ("user" if i % 2 == 0 else "assistant")
                or not isinstance(t["content"], str) or not t["content"].strip() for i, t in enumerate(history))
            or history[-1]["role"] != "user"):
        raise ValueError("Invalid candidate conversation")
    messages = [{"role": "system", "content": instruction}, *deepcopy(history)]
    if provider == "grok":
        return {"model": model, "input": messages, "store": False,
                "max_output_tokens": output_limit, "temperature": 0.7, "top_p": 0.95}
    if provider == "gemini":
        sections = [f'<{t["role"]} turn="{i + 1}">\n{t["content"]}\n</{t["role"]}>' for i, t in enumerate(history)]
        return {"model": model, "system_instruction": instruction, "store": False,
            "input": "Conversation so far (reply only to the final user turn):\n\n" + "\n\n".join(sections),
            "generation_config": {"max_output_tokens": output_limit, "thinking_level": "medium"},
            "service_tier": "standard"}
    if provider == "minimax":
        # M3 fixes sampling internally. Do not pretend a shared temperature is effective.
        return {"model": model, "messages": messages, "max_completion_tokens": output_limit,
                "reasoning_split": True, "service_tier": "standard"}
    raise ValueError("Unknown provider")


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_exclusive(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_dir(path.parent)


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class FixtureJournal:
    """Serial, fresh-directory-only simulation of durable prospective accounting.

    Supplied bytes are written before parsing. No HTTP headers, keys, URLs or
    external callables are accepted. A crash leaves a reserved attempt on disk;
    there is no resume constructor. All raw/rejected replies stay local.
    """

    def __init__(self, directory, protocol_sha256, max_attempts, budget_microusd):
        self.max_attempts = positive_integer(max_attempts)
        self.budget = positive_integer(budget_microusd)
        if (not isinstance(protocol_sha256, str) or len(protocol_sha256) != 64
                or any(c not in "0123456789abcdef" for c in protocol_sha256)):
            raise ValueError("Invalid protocol fingerprint")
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        _sync_dir(self.directory.parent)
        self.attempts = self.reserved = 0
        self.stopped = False
        self.lock = threading.Lock()
        self.protocol = protocol_sha256
        _write_exclusive(self.directory / "run.json", _json_bytes({
            "mode": "offline_fixture_only", "protocol_sha256": protocol_sha256,
            "max_fixture_attempts": max_attempts, "budget_microusd": budget_microusd,
            "automatic_retries": 0, "resume_allowed": False, "live_calls": 0}))

    def record(self, model, payload, reservation_microusd, reply, validator, status=200):
        """reply is bytes or an exception fixture, never a transport function."""
        with self.lock:
            if self.stopped:
                raise AdmissionBlocked("Run stopped; no retry or resume")
            positive_integer(reservation_microusd)
            if self.attempts >= self.max_attempts or self.reserved + reservation_microusd > self.budget:
                self.stopped = True
                _write_exclusive(self.directory / "stopped.json", _json_bytes({
                    "category": "pre_dispatch_budget_or_attempt_limit", "fixture_attempts": self.attempts,
                    "reserved_microusd": self.reserved, "live_calls": 0}))
                raise AdmissionBlocked("Insufficient prospective budget or attempt allowance")
            if (not isinstance(payload, dict) or payload.get("model") != model
                    or not isinstance(model, str) or not model.strip()
                    or not isinstance(reply, (bytes, BaseException)) or type(status) is not int):
                raise ValueError("Invalid fixture input")
            payload_bytes = _json_bytes(payload)
            self.attempts += 1
            self.reserved += reservation_microusd
            number = f"{self.attempts:04d}"
            attempt = {"mode": "offline_fixture_only", "sequence": self.attempts,
                "protocol_sha256": self.protocol, "model_requested": model,
                "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
                "reservation_microusd": reservation_microusd, "cumulative_reserved_microusd": self.reserved,
                "retry": False, "delivery_state": "reserved_before_simulated_dispatch"}
            # An incomplete write is terminal too. Never dispatch after a failed durable write.
            self.stopped = True
            _write_exclusive(self.directory / f"{number}.attempt.json", _json_bytes(attempt))
            _write_exclusive(self.directory / f"{number}.payload.json", payload_bytes)
            category = "transport_or_interruption"
            raw_hash = None
            try:
                if isinstance(reply, BaseException):
                    raise reply
                _write_exclusive(self.directory / f"{number}.raw.bin", reply)
                raw_hash = hashlib.sha256(reply).hexdigest()
                category = "http"
                if not 200 <= status < 300:
                    raise ValueError("Rejected HTTP status")
                category = "json_format"
                def reject_constant(value):
                    raise ValueError("Nonfinite JSON number")
                decoded = json.loads(reply.decode("utf-8"), object_pairs_hook=_strict_object,
                                     parse_constant=reject_constant)
                category = "model_identity"
                if not isinstance(decoded, dict) or decoded.get("model") != model:
                    raise ValueError("Returned model identity mismatch")
                category = "response_validation"
                accepted = validator(decoded)
                _write_exclusive(self.directory / f"{number}.accepted.json", _json_bytes({
                    "raw_sha256": raw_hash, "result": accepted, "status": status}))
            except BaseException as exc:
                # Never log str(exc), which could contain credentials or response text.
                _write_exclusive(self.directory / f"{number}.rejected.json", _json_bytes({
                    "category": category, "error_type": type(exc).__name__, "raw_sha256": raw_hash,
                    "status": status if raw_hash else None, "reservation_released": False}))
                _write_exclusive(self.directory / "stopped.json", _json_bytes({
                    "category": category, "fixture_attempts": self.attempts,
                    "reserved_microusd": self.reserved, "live_calls": 0}))
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                return {"accepted": False, "category": category}
            self.stopped = False
            return {"accepted": True, "result": accepted}
