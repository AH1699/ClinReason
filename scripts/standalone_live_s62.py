"""Approval-bound O/P/Q pilot; fresh single-use allowance, never retry or resume.

S60/S61 and all historical runs stay unchanged. Public preflight needs no key.
Approval records attest the trusted local operator's receipt of human consent;
they are not authentication against a hostile user of the same OS account.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.client import HTTPSConnection
import json
from pathlib import Path
import ssl
import subprocess
import threading
from uuid import UUID

from benchmark.local_settings import read_setting
from benchmark.live_s41 import _private_path
from scripts import standalone_rehearsal_s61 as previous
from scripts.minimax_accounting_s46 import PRIORITY_RATES

base, pilot, capture, guard = previous.engine, previous.pilot, previous.capture, previous.guard
VERSION = "s62-standalone-live-v1"
PLAN = "config/standalone_live_s62_v1.json"
FREEZE = "config/standalone_live_s62_frozen_v1.json"
FILES = (PLAN, "scripts/standalone_live_s62.py", "tests/test_standalone_live_s62.py",
         "benchmark/local_settings.py", "benchmark/live_s41.py")
PRICE_URLS = {"gemini": "https://ai.google.dev/gemini-api/docs/pricing",
              "minimax": "https://platform.minimax.io/docs/pricing/overview"}
MODEL_URLS = {"gemini": "https://ai.google.dev/gemini-api/docs/interactions-overview",
              "minimax": "https://platform.minimax.io/docs/api-reference/text-openai-api"}
GATE = {"accepted_records": 96, "unsafe_error_matches": 16, "safe_or_initial_records_with_errors": 0,
        "minimum_matching_repeat_vectors": 31, "expected_repeat_pairs": 32,
        "numeric_order_required": False, "clinical_validation": False}
KEY_NAMES = {"gemini": "GEMINI_API_KEY", "minimax": "MINIMAX_API_KEY"}
read, write, digest = previous.read, previous.write, previous.digest


def stamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp required")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def plan(root):
    value = read(Path(root) / PLAN)
    expected = {"version": VERSION, "status": "ready_for_explicit_approval", "maximum_attempts": 480,
        "stop_threshold_usd": "20.00", "hard_ceiling": False, "last_request_overrun_possible": True,
        "automatic_retries": 0, "resume_allowed": False, "maximum_development_format_failures": 3,
        "control_gate": GATE}
    if set(value) != set(expected) | {"pricing_verification"} or any(
            guard._json_bytes(value[k]) != guard._json_bytes(v) for k, v in expected.items()):
        raise ValueError("Changed prospective scope, threshold or gates")
    spec = pilot.inputs(Path(root))[0]
    models = {s["model"]: s for s in base.workflow.design(root)["candidates"]
              if s["model"] in {m["model"] for m in spec["candidate_roster_proposal"]}}
    price = value["pricing_verification"]
    fixed = {"sources": PRICE_URLS, "availability_sources": MODEL_URLS, "models": models,
        "m3_default_echo_monitoring": PRIORITY_RATES, "input_token_scope_max": 16000,
        "cache_discount_used": False, "output_includes_thinking": True, "account_access_tested": False}
    if (not isinstance(price, dict) or set(price) != set(fixed) | {"verified_at", "verified_by", "evidence_note"}
            or any(guard._json_bytes(price[k]) != guard._json_bytes(v) for k, v in fixed.items())
            or any(not isinstance(price[k], str) or not price[k].strip() for k in ("verified_by", "evidence_note"))):
        raise ValueError("Official price/availability evidence must match accounting")
    stamp(price["verified_at"])
    return value


def snapshot(root):
    root = Path(root)
    return {"version": VERSION, "s61": previous.snapshot(root), "plan": plan(root),
        "files": {p: digest(pilot.public_path(root, p).read_bytes()) for p in FILES},
        "endpoints": {p: list(capture.ENDPOINTS[p]) for p in KEY_NAMES},
        "reporting": "all_64_clinically_held_first_repeat_separate_missing_not_zero_no_ranking"}


def validate_authorization(root, freeze, approval, now=None):
    now = now or datetime.now(timezone.utc)
    current = snapshot(root)
    if guard._json_bytes(current) != guard._json_bytes(freeze):
        raise ValueError("Prospective protocol differs")
    spec = current["plan"]
    checked_at = stamp(spec["pricing_verification"]["verified_at"])
    if not timedelta(0) <= now - checked_at <= timedelta(hours=24):
        raise ValueError("Public price and model evidence must be checked within 24 hours")
    protocol = pilot.sha256_json(current)
    flags = {"accept_paid_calls", "accept_provider_disclosure", "accept_threshold_overrun",
             "accept_control_and_failure_gates", "accept_provisional_reporting"}
    fields = flags | {"approval_id", "run_id", "protocol_sha256", "approved_at", "expires_at",
                      "approved_by", "authorization_evidence"}
    if (not isinstance(approval, dict) or set(approval) != fields
            or approval["protocol_sha256"] != protocol
            or any(approval[k] is not True for k in flags)
            or any(not isinstance(approval[k], str) or not approval[k].strip()
                   for k in ("approved_by", "authorization_evidence"))
            or any(str(UUID(approval[k])) != approval[k] for k in ("approval_id", "run_id"))
            or not checked_at <= stamp(approval["approved_at"]) <= now < stamp(approval["expires_at"])
            or stamp(approval["expires_at"]) - stamp(approval["approved_at"]) > timedelta(hours=24)):
        raise ValueError("Fresh explicit owner approval for this exact scope is required")
    return {"protocol_sha256": protocol, "plan": spec}


def consume_approval(root, approval, protocol):
    if (approval["protocol_sha256"] != protocol or any(str(UUID(approval[k])) != approval[k]
            for k in ("approval_id", "run_id"))):
        raise ValueError("Canonical approval/run binding required")
    parent = _private_path(root, "work/s62-consumed-approvals", directory=True, create=True)
    target = parent / (approval["approval_id"] + ".json")
    if subprocess.run(["git", "check-ignore", "-q", "--", str(target)], cwd=root, capture_output=True).returncode:
        raise ValueError("Approval receipts must be ignored")
    write(target, {"version": VERSION, "approval": approval, "protocol_sha256": protocol,
                   "consumed_before_credentials_or_network": True, "resume_allowed": False})


class Core(base.Engine):
    """Same request/score semantics with prospective admission and failure limits."""
    def __init__(self, root, threshold):
        super().__init__(root, mode="offline_transport_fixture", fixture_threshold_usd=threshold)
        self.format_failures = 0

    def gate(self):
        value = self.control_readout()
        safe_errors = [r["job_id"] for r in value["stage_results"]
                       if r["profile"] in (None, "safe") and r["critical_errors"]]
        checks = {"all_controls_valid": value["accepted_records"] == 96,
                  "all_unsafe_hypotheses_detected": value["observed_unsafe_error_matches"] == 16,
                  "safe_and_initial_without_errors": not safe_errors,
                  "repeat_vectors_at_least_31_of_32": value["matching_repeat_criterion_error_vectors"] >= 31}
        return {"pass": all(checks.values()), "checks": checks,
                "safe_or_initial_records_with_errors": safe_errors,
                "scope": "provisional_author_control_screen_not_clinical_validation", "policy": GATE}

    def prepare(self):
        if self.pending is not None:
            raise ValueError("One reply is pending")
        if not self.terminal and self.index >= 96 and not self.gate()["pass"]:
            self.terminal = "prospective_control_gate_failed"
            return None
        return super().prepare()

    def consume(self, result, raw_bytes):
        row = deepcopy(self.pending)
        format_only = False
        if row and row["kind"].startswith("judge") and result["category"] == "response_validation":
            try:
                self.decode(capture.strict_json(raw_bytes))
            except base.score.JudgmentFailure as exc:
                format_only = exc.category == "format"
        outcome = super().consume(result, raw_bytes)
        if self.terminal == "simulated_spend_threshold_reached":
            self.terminal = "spend_threshold_reached"
        if result["category"] == "model_identity":
            self.terminal = "model_identity_failure"
        if format_only and self.terminal == "invalid_judge_reply":
            self.format_failures += 1
            self.terminal = ("development_format_failure_limit" if self.format_failures >= 3 else None)
        if not self.terminal and self.monitored >= self.threshold:
            self.terminal = "spend_threshold_reached"
        return outcome


def report(core, mode):
    value = core.report()
    fixture = mode == "offline_fixture"
    attempts = value.pop("settled_fixture_attempts")
    value.pop("numeric_fixture_scores_only")
    money = value.pop("simulated_monitoring_usd")
    unknown = value.pop("unknown_simulated_cost_attempts")
    value.update(version=VERSION, mode=mode, simulation_only=fixture,
        live_calls=0 if fixture else attempts + value["unresolved_reservations"],
        live_call_count_basis="reserved_attempts_may_not_have_reached_provider",
        measured_model_scores=0 if fixture else sum(
            c[p]["score"] is not None for c in value["conversations"] for p in ("first", "repeat")),
        numeric_fixture_scores_only=fixture, settled_attempts=attempts,
        monitoring_usd=money, unknown_cost_attempts=unknown, hard_ceiling=False,
        last_request_overrun_possible=True, development_format_failures=core.format_failures,
        prospective_control_gate=core.gate())
    value["control_readout"]["clinical_gate"] = "not_clinically_validated_prospective_screen_only"
    value["control_readout"]["meaning"] = "Author-control diagnostics; not clinical truth"
    return value


def reservation(core, before, request, mode):
    value = previous.reservation(core, before, request)
    value.update(delivery="reserved_before_transport", simulation_only=mode == "offline_fixture")
    return value


def settled(core, outcome, result, directory):
    return {**previous.settled(core, outcome, result, directory), "development_format_failures": core.format_failures}


def tls(host, *, timeout):
    if host not in {capture.ENDPOINTS[p][0] for p in KEY_NAMES}:
        raise ValueError("Unapproved host")
    return HTTPSConnection(host, timeout=timeout, context=ssl.create_default_context())


class Session:
    def __init__(self, root, directory, *, mode, freeze=None, approval=None):
        if mode not in {"live", "offline_fixture"}:
            raise ValueError("Explicit execution mode required")
        self.root, self.mode = Path(root), mode
        self.freeze, self.approval = deepcopy(freeze), deepcopy(approval)
        frozen = snapshot(self.root)
        self.protocol = pilot.sha256_json(frozen)
        if mode == "live":
            validate_authorization(self.root, freeze, approval)
            expected = self.root / "work/s62-runs" / approval["run_id"]
            if Path(directory).absolute() != expected.absolute():
                raise ValueError("Live run path must match approved run ID")
            _private_path(self.root, "work/s62-runs", directory=True, create=True)
            self.directory = _private_path(self.root, "work/s62-runs/" + approval["run_id"])
            if self.directory.exists() or subprocess.run(["git", "check-ignore", "-q", "--", str(self.directory)],
                    cwd=root, capture_output=True).returncode:
                raise ValueError("New ignored live directory required")
            consume_approval(self.root, approval, self.protocol)
        else:
            if freeze is not None or approval is not None:
                raise ValueError("Fixture mode cannot carry a paid approval")
            self.directory = previous.safe_directory(self.root, directory)
        self.core = Core(self.root, frozen["plan"]["stop_threshold_usd"])
        self.input_pins = {**self.core.parent["files"], **frozen["s61"]["files"], **frozen["files"],
                           pilot.MANIFEST: digest((self.root / pilot.MANIFEST).read_bytes())}
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        write(self.directory / "manifest.json", {"snapshot": frozen, "protocol_sha256": self.protocol,
            "mode": mode, "approval": approval, "resume_allowed": False})
        (self.directory / "events").mkdir(mode=0o700)
        guard._sync_dir(self.directory)
        self.lock, self.poisoned, self.closed, self.event = threading.Lock(), False, False, 0

    def step(self, fixture=None):
        with self.lock:
            if self.poisoned:
                raise ValueError("Interrupted writer; no retry/resume")
            if self.closed:
                return None
            if self.mode == "offline_fixture":
                if type(fixture) is not previous.Fixture:
                    raise ValueError("Built-in fixture required; no external transport")
                fixture.check()
                fixture = deepcopy(fixture)
            elif fixture is not None:
                raise ValueError("No fixture or supplied connection in live mode")
            self.poisoned = True
            if any(digest(pilot.public_path(self.root, p).read_bytes()) != h for p, h in self.input_pins.items()):
                raise ValueError("Bound inputs changed; no dispatch")
            if self.mode == "live":
                validate_authorization(self.root, self.freeze, self.approval)
            before = self.core.index
            request = self.core.prepare()
            if request is None:
                write(self.directory / "report.json", report(self.core, self.mode))
                self.closed, self.poisoned = True, False
                return None
            self.event += 1
            event = self.directory / "events" / f"{self.event:04d}"
            event.mkdir(mode=0o700)
            guard._sync_dir(event.parent)
            write(event / "reservation.json", reservation(self.core, before, request, self.mode))
            context = request["context"]
            write(event / "payload.json", context["payload"])
            journal = capture.CaptureJournal(self.root, event / "transport", 1, self.protocol, self.mode)
            def factory(host, *, timeout):
                if host != capture.ENDPOINTS[context["provider"]][0] or timeout != journal.policy["socket_timeout_seconds"]:
                    raise ValueError("Unexpected endpoint or timeout")
                if fixture.fault == "connect_timeout":
                    raise TimeoutError("Fixture timeout")
                return previous.fake._Connection(fixture)
            credential = None
            try:
                credential = ("S62-FIXTURE-ONLY" if self.mode == "offline_fixture" else
                    read_setting(self.root / ".env.local", KEY_NAMES[context["provider"]], secret=True))
                result = journal.exchange(context["provider"], context["payload"], self.core.decode,
                    credential=credential, connection_factory=factory if self.mode == "offline_fixture" else tls)
            finally:
                credential = None
            raw = event / "transport/0001.raw.bin"
            outcome = self.core.consume(result, raw.read_bytes() if raw.exists() else b"")
            write(event / "result.json", settled(self.core, outcome, result, event / "transport"))
            if self.core.terminal:
                write(self.directory / "report.json", report(self.core, self.mode))
                self.closed = True
            self.poisoned = False
            return {"event": self.event, "outcome": outcome, "terminal": self.core.terminal,
                    "monitoring_usd": str(Decimal(self.core.monitored) / base.TICKS_PER_USD),
                    "mode": self.mode, "development_format_failures": self.core.format_failures}


def reconstruct_capture(core, directory, protocol, mode):
    """Read raw journal bytes independently; do not trust saved parsed judgments."""
    files = previous.capture_hashes(directory)
    required = {"run.json", "0001.attempt.json", "0001.payload.json", "0001.capture.json", "0001.accounting.json"}
    if not required <= set(files) or ("0001.accepted.json" in files) == ("0001.rejected.json" in files):
        return None
    context = core.contexts[core.pending["id"]]
    payload = context["payload"]
    fixture = mode == "offline_fixture"
    if (read(directory / "run.json") != {"mode": mode, "automatic_retries": 0, "max_attempts": 1,
            "protocol_sha256": protocol, "resume_allowed": False, "costs_are_simulated": fixture}
            or read(directory / "0001.attempt.json") != {"sequence": 1, "provider": context["provider"],
                "model": context["model"], "protocol_sha256": protocol,
                "payload_sha256": digest(guard._json_bytes(payload)), "delivery": "reserved_before_connection",
                "prospective_cost_bound": None, "automatic_retries": 0, "fixture_only": fixture}
            or (directory / "0001.payload.json").read_bytes() != guard._json_bytes(payload)):
        raise ValueError("Capture request/protocol differs")
    meta = read(directory / "0001.capture.json")
    raw = (directory / "0001.raw.bin").read_bytes() if "0001.raw.bin" in files else b""
    if (meta["bytes_saved"] != len(raw) or meta["mode"] != mode or meta["fixture_only"] is not fixture
            or meta["body_sha256"] != (digest(raw) if meta["delivery"] == "response_received" else None)):
        raise ValueError("Capture body/mode differs")
    category, parsed = meta["category"], None
    account = capture.account(None, core.model_specs[context["provider"], context["model"]], payload)
    if category in previous.fake.BODY_CATEGORIES:
        if type(meta["status"]) is not int or not 200 <= meta["status"] < 300 or meta["body_eof"] is not True:
            raise ValueError("Only complete 2xx responses may enter decoder")
        expected = "json_format"
        try:
            raw_json = capture.strict_json(raw)
            account = capture.account(raw_json, core.model_specs[context["provider"], context["model"]], payload)
            expected = "model_identity"
            if not isinstance(raw_json, dict) or raw_json.get("model") != context["model"]:
                raise ValueError("Identity mismatch")
            expected = "usage_accounting"
            if account["status"] == "unknown":
                raise ValueError("Unknown usage")
            expected = "response_validation"
            parsed = core.decode(raw_json)
            expected = "accepted"
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, UnicodeDecodeError):
            pass
        if expected != category:
            raise ValueError("Reconstructed category differs")
    elif "0001.accepted.json" in files:
        raise ValueError("Failed transport cannot have accepted result")
    if read(directory / "0001.accounting.json") != account:
        raise ValueError("Reconstructed accounting differs")
    if category == "accepted":
        expected = {"result": parsed, "raw_sha256": digest(raw)}
        name = "0001.accepted.json"
    else:
        expected = {"category": category, "exception_text_retained": False, "charge_may_have_occurred": True, "retry": False}
        name = "0001.rejected.json"
    if read(directory / name) != expected:
        raise ValueError("Interpretation differs from raw reply")
    return {"category": category, "accepted": category == "accepted", "result": parsed, "accounting": account}, raw


def replay(root, directory):
    root = Path(root)
    directory = previous.safe_directory(root, directory)
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()) or path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("Linked/nonregular journal artifact")
    names = {p.name for p in directory.iterdir()}
    if not {"manifest.json", "events"} <= names or names - {"manifest.json", "events", "report.json"}:
        raise ValueError("Incomplete/unexpected journal root")
    manifest = read(directory / "manifest.json")
    frozen = snapshot(root)
    protocol = pilot.sha256_json(frozen)
    mode, approval = manifest["mode"], manifest["approval"]
    if mode not in {"offline_fixture", "live"} or manifest != {"snapshot": frozen, "protocol_sha256": protocol,
            "mode": mode, "approval": approval, "resume_allowed": False}:
        raise ValueError("Journal protocol differs")
    if mode == "live":
        # Expired records remain inspectable. Validate at their recorded consent time.
        validate_authorization(root, frozen, approval, now=stamp(approval["approved_at"]))
        expected = root / "work/s62-runs" / approval["run_id"]
        receipt = _private_path(root, "work/s62-consumed-approvals/" + approval["approval_id"] + ".json")
        if directory != expected or receipt.stat().st_nlink != 1 or read(receipt) != {
                "version": VERSION, "approval": approval, "protocol_sha256": protocol,
                "consumed_before_credentials_or_network": True, "resume_allowed": False}:
            raise ValueError("Live approval/run receipt differs")
    elif approval is not None:
        raise ValueError("Fixture journal with paid approval")
    core = Core(root, frozen["plan"]["stop_threshold_usd"])
    events = sorted((directory / "events").iterdir())
    if len(events) > 480 or any(not p.is_dir() or p.name != f"{i:04d}" for i, p in enumerate(events, 1)):
        raise ValueError("Invalid event sequence")
    partial = None
    for event in events:
        if partial is not None or core.terminal:
            raise ValueError("Event after interruption/stop")
        names = {p.name for p in event.iterdir()}
        order = ["reservation.json", "payload.json", "transport", "result.json"]
        if names not in [set(order[:i]) for i in range(5)]:
            raise ValueError("Orphan/reordered event artifact")
        before = core.index
        request = core.prepare()
        if request is None:
            raise ValueError("Event beyond permitted schedule")
        partial = "interrupted_before_reservation"
        if "reservation.json" not in names:
            continue
        if read(event / "reservation.json") != reservation(core, before, request, mode):
            raise ValueError("Reservation/context differs")
        partial = "interrupted_before_payload"
        if "payload.json" not in names:
            continue
        if (event / "payload.json").read_bytes() != guard._json_bytes(request["context"]["payload"]):
            raise ValueError("Payload differs")
        partial = "interrupted_before_complete_capture"
        if "transport" not in names:
            continue
        captured = reconstruct_capture(core, event / "transport", protocol, mode)
        if captured is None:
            if "result.json" in names:
                raise ValueError("Result without complete capture")
            continue
        result, raw = captured
        outcome = core.consume(result, raw)
        partial = "captured_reply_reconstructed_without_result"
        if "result.json" not in names:
            continue
        if read(event / "result.json") != settled(core, outcome, result, event / "transport"):
            raise ValueError("Reconstructed outcome differs")
        partial = None
    path = directory / "report.json"
    if path.exists():
        if partial is not None or not core.terminal and core.prepare() is not None:
            raise ValueError("Report before terminal state")
        if read(path) != report(core, mode):
            raise ValueError("Report differs from raw reconstruction")
    return {"version": VERSION, "protocol_sha256": protocol, "read_only": True, "resume_allowed": False,
            "events": len(events), "incomplete_tail": partial, "report_verified": path.exists(), "report": report(core, mode)}


def proposal(root):
    spec = plan(root)
    models = spec["pricing_verification"]["models"]
    scenarios = []
    for tokens in (4000, 8000):
        total = Decimal(0)
        for model, count in [("gemini-3.8-flash", 352), *[(m, 32) for m in models]]:
            rates = PRIORITY_RATES if model == "MiniMax-M3" else models[model]
            total += Decimal(count * tokens) * (Decimal(str(rates["input_per_million"])) +
                Decimal(str(rates["output_per_million"]))) / 1000000
        scenarios.append({"assumed_input_tokens_per_request": tokens,
            "assumed_billed_output_tokens_including_thinking_per_request": tokens, "estimated_usd": str(total)})
    return {"version": VERSION, "maximum_attempts": 480, "candidate_turns": 128, "judge_requests": 352,
        "conversations": 64, "proposed_stop_threshold_usd": spec["stop_threshold_usd"],
        "hard_ceiling": False, "last_request_overrun_possible": True,
        "cost_scenarios_not_predictions": scenarios, "completion_within_budget_guaranteed": False,
        "live_authorized": False, "live_calls": 0, "control_gate": GATE,
        "pricing_verification": spec["pricing_verification"]}


def run_live(root, freeze, approval):
    directory = Path(root) / "work/s62-runs" / approval["run_id"]
    session = Session(root, directory, mode="live", freeze=freeze, approval=approval)
    try:
        while True:
            progress = session.step()
            if progress is None:
                break
            print(json.dumps(progress), flush=True)
    except BaseException:
        raise guard.AdmissionBlocked("Stopped; approval consumed. Inspect saved prefix; do not retry/resume.") from None
    return replay(root, directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("proposal", "snapshot", "preflight", "run", "replay"))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "proposal":
        value = proposal(root)
    elif args.command == "snapshot":
        value = snapshot(root)
    elif args.command == "replay":
        if args.directory is None:
            parser.error("replay requires --directory")
        value = replay(root, args.directory)
    else:
        if args.freeze is None or args.approval is None:
            parser.error("preflight/run require --freeze and --approval")
        # Owner approvals are private; this command never creates consent records.
        relative = args.approval.absolute().relative_to(root)
        path = _private_path(root, str(relative))
        if path.stat().st_nlink != 1:
            raise ValueError("Regular private approval file required")
        freeze, approval = read(args.freeze), read(path)
        value = (run_live(root, freeze, approval) if args.command == "run" else
                 validate_authorization(root, freeze, approval))
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
